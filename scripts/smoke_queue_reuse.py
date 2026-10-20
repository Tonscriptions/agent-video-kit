"""Real native CLI batch reuse; procedural input and independent media checks."""
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
from datetime import datetime, timezone

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_frozen_regression import frozen

W, H, FPS, FRAMES = 320, 180, 12, 24


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--font', type=Path, required=True)
    p.add_argument('--font-license', type=Path, required=True)
    p.add_argument('--installed', type=Path)
    args = p.parse_args()
    work, evidence, assets = (v.resolve() for v in (args.work, args.evidence, args.assets))
    if any(v.exists() for v in (work, evidence, assets)):
        raise ValueError('Choose new work, evidence and media directories')
    for path in (work, evidence, assets):
        path.mkdir(parents=True)
    (ROOT / 'product/.runtime/temp').mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(TEMP=str(ROOT / 'product/.runtime/temp'), TMP=str(ROOT / 'product/.runtime/temp'),
               TMPDIR=str(ROOT / 'product/.runtime/temp'), PYTHONDONTWRITEBYTECODE='1')
    prefix = ([sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(args.installed.resolve() / 'run.py')]
              if args.installed else [sys.executable, '-E', '-B', '-X', 'utf8', '-c',
              'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;sys.exit(main())',
              str(ROOT / 'product/src')])
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'native_windows': sys.platform == 'win32', 'virtualization': False,
              'installed': str(args.installed.resolve()) if args.installed else None,
              'calls': [], 'checks': [], 'frozen_before': frozen(), 'goal_complete': False,
              'script_sha256': sha(__file__)}
    def save():
        write(evidence / 'verification.json', record)
    save()
    def check(name, condition, **details):
        record['checks'].append({'name': name, 'ok': bool(condition), **details})
        save()
        if not condition:
            raise AssertionError(name)
    def run(label, command, *, data=None, expect=0, binary=False):
        started = time.monotonic()
        result = subprocess.run([str(v) for v in command], cwd=ROOT, env=env,
                                input=data, capture_output=True, timeout=600)
        row = {'label': label, 'command': [str(v) for v in command], 'exit_code': result.returncode,
               'seconds': time.monotonic() - started, 'stdout_bytes': len(result.stdout),
               'stdout_sha256': hashlib.sha256(result.stdout).hexdigest()}
        if not binary:
            (evidence / f'{label}.stdout.log').write_bytes(result.stdout)
        (evidence / f'{label}.stderr.log').write_bytes(result.stderr)
        record['calls'].append(row)
        save()
        if result.returncode != expect:
            raise AssertionError(f'{label}: {result.returncode} != {expect}: {result.stderr[-2000:]!r}')
        return result.stdout
    def cli(label, *command, expect=0):
        raw = run(label, [*prefix, *command], expect=expect)
        rows = [json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
        events = []
        for line in (evidence / f'{label}.stderr.log').read_text(encoding='utf-8-sig').splitlines():
            if line.startswith('{'):
                events.append(json.loads(line))
        return rows[-1], events
    def decode(label, path, *, alpha=False):
        decoder = ['-c:v', 'libvpx-vp9'] if alpha else []
        raw = run(label + '-rgba', ['ffmpeg', '-hide_banner', '-loglevel', 'error', *decoder,
                    '-i', path, '-map', '0:v:0', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1'], binary=True)
        info = json.loads(run(label + '-pts', ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'frame=best_effort_timestamp_time,pkt_duration_time', '-of', 'json', path]))
        probe = json.loads(run(label + '-probe', ['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path]))
        stream = next(v for v in probe['streams'] if v['codec_type'] == 'video')
        frame_bytes = int(stream['width']) * int(stream['height']) * 4
        check(label + '-complete-frames', len(raw) % frame_bytes == 0)
        pcm = run(label + '-pcm', ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', path,
            '-map', '0:a:0', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1'], binary=True)
        return {'rgba_sha256': hashlib.sha256(raw).hexdigest(), 'frames': len(raw) // frame_bytes,
                'frame_sha256': [hashlib.sha256(raw[i:i+frame_bytes]).hexdigest() for i in range(0, len(raw), frame_bytes)],
                'alpha_min': min(raw[3::4]), 'alpha_max': max(raw[3::4]), 'pts': info['frames'],
                'pcm_sha256': hashlib.sha256(pcm).hexdigest(), 'pcm_float_values': len(pcm) // 4,
                'probe': probe, '_rgba': raw, '_frame_bytes': frame_bytes}
    try:
        frames = []
        for n in range(FRAMES):
            image = Image.new('RGBA', (W, H), (14, 24, 39, 0))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((12+n*5, 45, 100+n*5, 133), radius=12, fill=(255, 160, 47, 255))
            draw.ellipse((180-n*3, 65, 238-n*3, 123), fill=(64, 200, 210, 180))
            for x in range(W):
                draw.line((x, H-18, x, H-1), fill=(48, 146, 250, round(x*255/(W-1))))
            frames.append(image.tobytes())
        source = assets / 'source.mkv'
        run('generate-source', ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo',
            '-pix_fmt', 'rgba', '-s', f'{W}x{H}', '-r', str(FPS), '-i', 'pipe:0', '-f', 'lavfi', '-i',
            'aevalsrc=0.1*sin(2*PI*220*t)|0.1*sin(2*PI*330*t):s=48000:d=2', '-shortest',
            '-c:v', 'ffv1', '-pix_fmt', 'bgra', '-c:a', 'pcm_s16le', source], data=b''.join(frames))
        source_decoded = decode('source', source)
        check('source-rgba-byte-exact', source_decoded['rgba_sha256'] == hashlib.sha256(b''.join(frames)).hexdigest())
        run('source-preview', ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', source,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', assets / 'source-preview.mp4'])
        shutil.copyfile(args.font, assets / 'DejaVuSans.ttf')
        shutil.copyfile(args.font_license, assets / 'LICENSE_DEJAVU')
        write(assets / 'source-origin.json', {'kind': 'procedural-fixture', 'source_license': 'CC0-1.0',
            'generator': str(Path(__file__).relative_to(ROOT)), 'generator_sha256': sha(__file__),
            'width': W, 'height': H, 'fps': FPS, 'frames': FRAMES, 'duration_seconds': 2,
            'font_source': str(args.font.resolve()), 'font_sha256': sha(args.font), 'font_license': 'LICENSE_DEJAVU',
            'no_remote_media': True, 'natural_footage': False})
        project = work / 'project'
        cli('project-init', 'project', 'init', project)
        for label, path, asset_id in (('video', source, 'source'), ('font', assets / 'DejaVuSans.ttf', 'font')):
            cli('ingest-' + label, 'media', 'ingest', '--project', project, '--input', path, '--asset-id', asset_id)
        # This is explicit authored project input, before any queue work.
        authored = json.loads((project / 'project.json').read_bytes())
        authored['settings']['canvas'].update(width=W, height=H)
        authored['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
        write(project / 'project.json', authored)
        changes = work / 'compose.json'
        write(changes, {'operations': [
            {'op': 'append_clip', 'id': 'picture', 'track_id': 'track_video_1', 'asset_id': 'source',
             'source_in_tick': 0, 'source_out_tick': 180000, 'duration_tick': 180000,
             'keyframes': [{'property': 'scale', 'keyframes': [{'at_tick': 0, 'value': .8, 'interpolation': 'linear'},
                            {'at_tick': 180000, 'value': 1., 'interpolation': 'linear'}]}],
             'subtitle': {'text': 'ONE ENCODE / REUSED COPY', 'style': {'font_asset_id': 'font', 'fontsize': 16,
                 'x': '12', 'y': '14', 'fontcolor': 'white', 'borderw': 1, 'bordercolor': 'black'}}},
            {'op': 'append_clip', 'id': 'sound', 'track_id': 'track_audio_1', 'asset_id': 'source',
             'source_in_tick': 0, 'source_out_tick': 180000, 'duration_tick': 180000},
        ]})
        cli('compose', 'timeline', 'compose', '--project', project, '--input', changes)
        jobs = work / 'jobs.json'
        write(jobs, {'jobs': [
            {'job_id': 'bad', 'output': 'renders/rejected.mp4', 'video_codec': 'fixture-invalid-codec'},
            {'job_id': 'first', 'output': 'renders/first.mp4'},
            {'job_id': 'copy', 'label': 'different filename', 'output': 'renders/renamed.mp4', 'crf': 18,
             'video_codec': 'libx264', 'pixel_format': 'yuv420p', 'hardware_encode': 'off'},
            {'job_id': 'smaller', 'output': 'renders/smaller.mp4', 'profile': 'custom', 'width': 256, 'height': 144},
            {'job_id': 'alpha-first', 'output': 'renders/alpha-first.webm', 'container': 'webm', 'crf': 0, 'pixel_format': 'yuva420p'},
            {'job_id': 'alpha-copy', 'output': 'renders/alpha-copy.webm', 'container': 'webm', 'crf': 0, 'pixel_format': 'yuva420p'},
        ]})
        cli('enqueue', 'queue', 'enqueue', '--project', project, '--input', jobs)
        before_dry = (project / 'operations/render-queue.json').read_bytes()
        cli('dry-run', 'queue', 'run', '--project', project, '--reuse-identical', '--dry-run')
        check('dry-run-preserves-queue', before_dry == (project / 'operations/render-queue.json').read_bytes())
        result, events = cli('queue-run', 'queue', 'run', '--project', project, '--reuse-identical',
                             '--continue-on-error', '--progress', 'jsonl', expect=2)
        record['queue_result'] = result
        record['events'] = events
        check('five-success-one-rejected', result['data']['summary']['succeeded'] == 5 and result['data']['summary']['failed'] == 1)
        check('three-encodes-two-copies', result['data']['reuse_summary']['encoded_successes'] == 3 and
              result['data']['reuse_summary']['reused_successes'] == 2)
        check('actual-progress-execution-counts', sum(e.get('type') == 'render_started' for e in events) == 3 and
              sum(e.get('type') == 'reuse_started' for e in events) == 2)
        rendered = {}
        for name in ('first.mp4', 'renamed.mp4', 'smaller.mp4', 'alpha-first.webm', 'alpha-copy.webm'):
            path = project / 'renders' / name
            shutil.copyfile(path, assets / name)
            shutil.copyfile(path.with_suffix(path.suffix + '.manifest.json'), assets / (name + '.manifest.json'))
            rendered[name] = decode(name.replace('.', '-'), path, alpha=name.endswith('.webm'))
        for first, second in (('first.mp4', 'renamed.mp4'), ('alpha-first.webm', 'alpha-copy.webm')):
            a, b = rendered[first], rendered[second]
            check(first + '-copy-file-equal', sha(assets / first) == sha(assets / second))
            check(first + '-copy-full-rgba-equal', a['frame_sha256'] == b['frame_sha256'] and a['frames'] == FRAMES)
            check(first + '-copy-pts-equal', a['pts'] == b['pts'])
            check(first + '-copy-pcm-equal', a['pcm_sha256'] == b['pcm_sha256'])
            manifest = json.loads((assets / (second + '.manifest.json')).read_bytes())
            check(second + '-honest-copy-provenance', manifest['reuse']['encoding_executed'] is False and manifest['command'] == [])
        check('alpha-not-opaque', rendered['alpha-copy.webm']['alpha_min'] == 0 and rendered['alpha-copy.webm']['alpha_max'] == 255)
        cli('inspect-copy', 'queue', 'inspect', '--project', project, '--job-id', 'copy')
        cli('validate', 'validate', '--project', project)
        cli('policy-audit', 'policy', 'audit', '--project', project)
        record['decoded'] = {k: {a: b for a, b in v.items() if not a.startswith('_')} for k, v in rendered.items()}
        record['source_decoded'] = {a: b for a, b in source_decoded.items() if not a.startswith('_')}
        # Static contact sheet uses actual encoded frames over an explicit checker.
        contact = Image.new('RGB', (W*3, H), '#dae0e6')
        for i, info in enumerate((source_decoded, rendered['first.mp4'], rendered['renamed.mp4'])):
            picture = Image.frombytes('RGBA', (W, H), info['_rgba'][:W*H*4])
            contact.paste(picture, (i*W, 0), picture)
        contact.save(assets / 'comparison-frame-0.png')
        run('comparison-gif', ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', assets / 'first.mp4',
            '-filter_complex', 'fps=6,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse', assets / 'preview.gif'])
        record['public_files'] = [{'path': v.relative_to(ROOT).as_posix(), 'bytes': v.stat().st_size, 'sha256': sha(v)}
                                  for v in sorted(assets.iterdir()) if v.is_file()]
        record['cli_calls'] = sum(row['command'][:len(prefix)] == prefix for row in record['calls'])
        record.update(status='passed', visual_review='pending', continuous_playback_review=False,
                      audio_listening_review=False, capcut_parity_accepted=False)
    except BaseException as exc:
        record.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), frozen_after=frozen())
        record['frozen_equal'] = record['frozen_before'] == record['frozen_after']
        save()
    if not record['frozen_equal']:
        raise AssertionError('Product input bytes changed during native execution')
    print(json.dumps({k: record[k] for k in ('status', 'cli_calls', 'frozen_equal')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
