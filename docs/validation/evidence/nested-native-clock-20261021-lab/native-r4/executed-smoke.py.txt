"""Public local CLI proof against independently generated native VFR intervals."""
from __future__ import annotations
import argparse
from bisect import bisect_left, bisect_right
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from PIL import Image, ImageDraw
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
W, H, TPS = 320, 180, 90000
RATE = Fraction(30000, 1001)
POINTS = [0, 33, 101, 188, 195, 441, 499, 800, 1002, 1221, 1600, 1800]


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def native_indexes(inputs):
    """Metadata embeds the same descriptor at more than one clock location."""
    unique = {}
    for row in walk(inputs):
        if row.get('protocol') == 'native-video-frame-index-v1' and 'source_index_decode_calls' in row:
            unique[json.dumps(row, sort_keys=True)] = row
    return list(unique.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'evidence', 'assets'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    work, evidence, assets = (getattr(args, n).resolve() for n in ('work', 'evidence', 'assets'))
    assert work.is_relative_to(ROOT / 'product/.runtime')
    assert evidence.is_relative_to(ROOT / 'docs/validation') and assets.is_relative_to(ROOT / 'docs/assets')
    assert not any(path.exists() for path in (work, evidence, assets))
    for path in (work, evidence, assets):
        path.mkdir(parents=True)
    (evidence / 'executed-smoke.py.txt').write_bytes(Path(__file__).read_bytes())
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'frozen_before': frozen(), 'calls': [], 'checks': [], 'cases': {},
              'native_windows': sys.platform == 'win32', 'virtualization': False, 'network': False,
              'continuous_playback_reviewed': False, 'audio_reviewed': False,
              'natural_video_quality_accepted': False, 'HDR_accepted': False,
              'general_nested_VFR_accepted': False, 'full_capcut_parity': False}
    def save():
        write(evidence / 'verification.json', record)
    def check(name, ok, **details):
        record['checks'].append({'name': name, 'ok': bool(ok), **details})
        save()
        assert ok, name
    env = dict(os.environ)
    temp = ROOT / 'product/.runtime/temp'
    temp.mkdir(parents=True, exist_ok=True)
    env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp), PYTHONDONTWRITEBYTECODE='1')
    def run(label, command, data=None):
        command = list(map(str, command))
        started = time.monotonic()
        result = subprocess.run(command, input=data, capture_output=True, env=env, cwd=ROOT, timeout=600)
        binary = label == 'source-decode' or label.endswith(('-preview-master', '-actual-encoded-frames'))
        if binary:
            write(evidence / (label + '.stdout-summary.json'), {'bytes': len(result.stdout),
                  'sha256': 'sha256:' + hashlib.sha256(result.stdout).hexdigest(),
                  'binary_pixels_retained': False, 'reproduction': 'Re-run the recorded native command.'})
        else:
            (evidence / (label + '.stdout.log')).write_bytes(result.stdout)
        (evidence / (label + '.stderr.log')).write_bytes(result.stderr)
        record['calls'].append({'label': label, 'command': command, 'exit_code': result.returncode,
                                'wall_seconds': time.monotonic() - started,
                                'stdout_sha256': 'sha256:' + hashlib.sha256(result.stdout).hexdigest()})
        save()
        assert result.returncode == 0, label + ': ' + (result.stderr + result.stdout)[-1500:].decode('utf8', 'replace')
        return result.stdout
    bootstrap = ('import sys;sys.path.insert(0,sys.argv.pop(1));'
                 'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
                 'from ai_ad_editor.cli import main;raise SystemExit(main())')
    prefix = ([sys.executable, '-I', '-S', '-B', '-X', 'utf8', args.installed.resolve() / 'run.py']
              if args.installed else
              [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap, ROOT / 'product/src'])
    def cli(label, *argv):
        return json.loads(run(label, [*prefix, *argv]))
    exe, probe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    assert exe and probe
    record.update(ffmpeg={'path': exe, 'sha256': sha(exe)}, ffprobe={'path': probe, 'sha256': sha(probe)})
    def decode(label, path):
        return run(label, [exe, '-v', 'error', '-i', path, '-an', '-fps_mode', 'passthrough',
                           '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1'])
    def authored(project):
        value = json.loads((project / 'project.json').read_bytes())
        selected = {k: value[k] for k in ('assets', 'settings', 'sequences')}
        return {'project': 'sha256:' + hashlib.sha256(json.dumps(selected, sort_keys=True,
                ensure_ascii=False).encode('utf8')).hexdigest(), 'rights': sha(project / 'rights-ledger.json')}
    def gif(path, frames, durations):
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=durations,
                       loop=0, disposal=2, optimize=False)
        with Image.open(path) as image:
            total = 0
            for n in range(image.n_frames):
                image.seek(n)
                total += image.info.get('duration', 0)
            return {'frames': image.n_frames, 'duration_ms': total,
                    'timing': 'GIF 10 ms grid; duplicate frames may coalesce'}
    try:
        colors = [(30 + n * 12, 50 + n * 7, 220 - n * 10, 255) for n in range(len(POINTS))]
        images = []
        for n, color in enumerate(colors):
            image = Image.new('RGBA', (W, H), color)
            draw = ImageDraw.Draw(image)
            draw.rectangle((15, 22, 280, 110), fill=(12, 18, 29, 255))
            draw.text((27, 35), 'ORIGINAL LOCAL VFR SOURCE', fill='white')
            draw.text((27, 58), f'FRAME {n:02d} / PTS {POINTS[n]} ms', fill='white')
            draw.text((27, 81), 'NATIVE PTS / NO CFR PREFILTER', fill='white')
            for bit in range(4):
                draw.rectangle((20 + bit * 65, 130, 65 + bit * 65, 160),
                               fill='white' if n & (1 << bit) else 'black')
            images.append(image)
        original = b''.join(image.tobytes() for image in images)
        expression = str(POINTS[-1])
        for n in range(len(POINTS) - 2, -1, -1):
            expression = f'if(eq(N,{n}),{POINTS[n]},{expression})'
        source = assets / 'source-native-vfr.nut'
        run('source-encode', [exe, '-v', 'error', '-n', '-f', 'rawvideo', '-pixel_format', 'rgba',
            '-video_size', f'{W}x{H}', '-framerate', '25', '-i', 'pipe:0', '-vf',
            "settb=1/1000,setpts='" + expression + "'", '-fps_mode', 'passthrough',
            '-enc_time_base', 'filter', '-c:v', 'ffv1', '-pix_fmt', 'bgra', source], original)
        check('independent-generated-source-entire-RGBA', decode('source-decode', source) == original)
        source_probe = json.loads(run('source-PTS', [probe, '-v', 'error', '-select_streams', 'v:0',
            '-show_frames', '-show_streams', '-show_entries', 'frame=pts,duration:stream=time_base', '-of', 'json', source]))
        native_tb = Fraction(source_probe['streams'][0]['time_base'])
        times = [int(frame['pts']) * native_tb for frame in source_probe['frames']]
        check('all-original-VFR-PTS', times == [Fraction(n, 1000) for n in POINTS])
        run('source-review', [exe, '-v', 'error', '-n', '-i', source, '-an', '-fps_mode', 'passthrough',
            '-enc_time_base', 'filter', '-c:v', 'libx264', '-crf', '12', '-pix_fmt', 'yuv444p',
            '-video_track_timescale', '90000', assets / 'source-review.mp4'])
        source_end = [*POINTS, POINTS[-1] + 40]
        source_delays = [10 * (round(source_end[n + 1] / 10) - round(source_end[n] / 10)) for n in range(len(images))]
        record['source_gif'] = gif(assets / 'source.gif', images, source_delays)
        for label, reverse, ramp, start, source_in in (
                ('forward-short-hold', False, False, 0, 17100),
                ('reverse-ramp', True, True, 9900, 10170)):
            project = work / label
            cli(label + '-init', 'project', 'init', project)
            cli(label + '-ingest', 'media', 'ingest', '--project', project, '--input', source,
                '--asset-id', 'source', '--source-url', 'local://nested-native-clock/original-source',
                '--license-spdx', 'CC0-1.0', '--license-url', 'local://nested-native-clock/CC0-1.0',
                '--verification-status', 'verified', '--permitted-use', 'commercial_ad',
                '--creator', 'agent-video-kit', '--evidence', 'Original generated geometric VFR frame cards; CC0-1.0')
            p = json.loads((project / 'project.json').read_bytes())
            p['settings']['canvas'] = {'width': W, 'height': H, 'background': '#000000'}
            p['settings']['timebase'] = {'ticks_per_second': TPS, 'display_fps': {'num': RATE.numerator, 'den': RATE.denominator}}
            write(project / 'project.json', p)
            with localcontext() as ctx:
                ctx.prec = 60
                duration = int((Decimal(3).ln() * TPS).to_integral_value()) if ramp else TPS
            request = {'operations': [
                {'op': 'add_sequence', 'id': 'child', 'duration_tick': 117000},
                {'op': 'append_clip', 'sequence_id': 'child', 'track_id': 'child_video_1',
                 'id': 'leaf', 'asset_id': 'source', 'timeline_start_tick': 0,
                 'duration_tick': 117000, 'source_in_tick': 0, 'source_out_tick': 117000},
                {'op': 'append_sequence_clip', 'sequence_id': 'seq_main', 'track_id': 'track_video_1',
                 'nested_sequence_id': 'child', 'id': 'parent', 'timeline_start_tick': start,
                 'duration_tick': duration, 'source_in_tick': source_in, 'source_out_tick': source_in + TPS,
                 'reverse': reverse, 'speed_curve': {'keyframes': [
                     {'at_tick': 0, 'speed': .5 if ramp else 1.}, {'at_tick': TPS, 'speed': 1.5 if ramp else 1.}]}},
                {'op': 'set_sequence_duration', 'sequence_id': 'seq_main', 'duration_tick': 135000, 'trim': False}]}
            write(assets / (label + '-request.json'), request)
            cli(label + '-compose', 'timeline', 'compose', '--project', project, '--input', assets / (label + '-request.json'))
            cli(label + '-validate', 'validate', '--project', project)
            before = authored(project)
            output = project / 'renders' / (label + '.mp4')
            result = cli(label + '-render', 'render', '--project', project, '--output', output,
                         '--profile', 'custom', '--width', W, '--height', H, '--crf', '0', '--pixel-format', 'yuv444p')['data']
            manifest = json.loads(Path(result['manifest']).read_bytes())
            write(evidence / (label + '-render-manifest.json'), manifest)
            shutil.copyfile(output, assets / (label + '.mp4'))
            check(label + '-published-MP4-equals-actual-render', sha(output) == sha(assets / (label + '.mp4')))
            clocks = [row for row in walk(manifest['inputs']) if row.get('source_clock_anchor') == 'original-native-intervals-before-nested-author-map']
            check(label + '-native-clock-is-used', len(clocks) == 1)
            indexes = native_indexes(manifest['inputs'])
            check(label + '-first-render-builds-shared-native-index', len(indexes) == 1
                  and indexes[0]['source_index_decode_calls'] == 1 and indexes[0]['status'] == 'built')
            repeated = cli(label + '-render-hit', 'render', '--project', project,
                           '--output', project / 'renders' / 'repeated.mp4', '--profile', 'custom',
                           '--width', W, '--height', H, '--crf', '0', '--pixel-format', 'yuv444p')['data']
            repeated_manifest = json.loads(Path(repeated['manifest']).read_bytes())
            write(evidence / (label + '-repeated-render-manifest.json'), repeated_manifest)
            hit_indexes = native_indexes(repeated_manifest['inputs'])
            check(label + '-second-render-skips-source-frame-probe', len(hit_indexes) == 1
                  and hit_indexes[0]['source_index_decode_calls'] == 0 and hit_indexes[0]['status'] == 'cache-hit')
            count = math.ceil(Fraction(135000, TPS) * RATE)
            preview = cli(label + '-preview', 'preview', 'range', '--project', project,
                          '--start-frame', 0, '--end-frame', count, '--height', H)['data']
            again = cli(label + '-preview-hit', 'preview', 'range', '--project', project,
                        '--start-frame', 0, '--end-frame', count, '--height', H)['data']
            check(label + '-preview-hit-keeps-key', again['cache_hit'] and again['cache_key'] == preview['cache_key'])
            expected, ids = [], []
            black = bytes((0, 0, 0, 255)) * (W * H)
            for n in range(count):
                now = Fraction(n) / RATE
                selected = -1
                if Fraction(start, TPS) <= now < Fraction(start + duration, TPS):
                    elapsed = now - Fraction(start, TPS)
                    if ramp:
                        with localcontext() as ctx:
                            ctx.prec = 60
                            ratio = elapsed / Fraction(duration, TPS)
                            progress = Decimal(ratio.numerator) / Decimal(ratio.denominator)
                            if reverse:
                                progress = 1 - progress
                            distance = Fraction(Decimal('.5') * ((Decimal(3).ln() * progress).exp() - 1))
                        source_time = Fraction(source_in, TPS) + distance
                    else:
                        source_time = Fraction(source_in, TPS) + elapsed
                    selected = (bisect_left(times, source_time) if reverse else bisect_right(times, source_time)) - 1
                ids.append(selected)
                expected.append(images[selected].tobytes() if selected >= 0 else black)
            expected_raw = b''.join(expected)
            master = decode(label + '-preview-master', preview['master'])
            check(label + '-complete-lossless-preview-RGBA', master == expected_raw,
                  bytes=len(master), expected_bytes=len(expected_raw))
            timing = json.loads(run(label + '-encoded-PTS', [probe, '-v', 'error', '-select_streams', 'v:0',
                '-show_frames', '-show_streams', '-show_entries', 'frame=pts:stream=time_base,width,height', '-of', 'json', output]))
            stream = timing['streams'][0]
            actual_pts = [int(row['pts']) * Fraction(stream['time_base']) for row in timing['frames']]
            check(label + '-all-encoded-PTS-and-raster', actual_pts == [Fraction(n) / RATE for n in range(count)]
                  and (stream['width'], stream['height']) == (W, H))
            decoded = decode(label + '-actual-encoded-frames', output)
            size = W * H * 4
            check(label + '-encoded-frame-count', len(decoded) == count * size)
            actual_images = [Image.frombytes('RGBA', (W, H), decoded[n * size:(n + 1) * size]) for n in range(count)]
            observed = []
            patch_errors = []
            for image, identity in zip(actual_images, ids):
                pixel = image.getpixel((W - 4, 10))
                observed.append(-1 if max(pixel[:3]) < 5 else min(range(len(colors)),
                    key=lambda i: sum(abs(a - b) for a, b in zip(pixel[:3], colors[i][:3]))))
                wanted = colors[identity] if identity >= 0 else (0, 0, 0, 255)
                patch_errors.append(max(abs(a - b) for a, b in zip(pixel, wanted)))
            check(label + '-encoded-every-frame-identity', observed == ids)
            check(label + '-authored-project-and-rights-unchanged', authored(project) == before)
            delays = [10 * (round((n + 1) * 1000 / float(RATE) / 10) - round(n * 1000 / float(RATE) / 10)) for n in range(count)]
            animation = gif(assets / (label + '.gif'), actual_images, delays)
            sheet = Image.new('RGB', (9 * 160, 5 * 90), '#101722')
            for n, image in enumerate(actual_images):
                sheet.paste(image.convert('RGB').resize((160, 90)), ((n % 9) * 160, (n // 9) * 90))
            sheet.save(assets / (label + '-all-frames.png'))
            write(assets / (label + '-editable-project.json'), json.loads((project / 'project.json').read_bytes()))
            record['cases'][label] = {'frames': count, 'fps': str(RATE), 'duration_tick': 135000,
                'expected_source_frame_ids': ids, 'encoded_source_frame_ids': observed,
                'preview_bytes': len(master), 'preview_max_RGBA_error': 0,
                'preview_sha256': 'sha256:' + hashlib.sha256(master).hexdigest(),
                'encoded_identity_patch_max_RGBA_error_observed': max(patch_errors),
                'encoded_full_frame_pixel_equality_claimed': False,
                'gif': animation, 'author_hashes_before_after': before}
            save()
        write(assets / 'rights.json', {'license': 'CC0-1.0', 'creator': 'agent-video-kit',
            'generator': 'scripts/smoke_nested_native_clock.py', 'source_native_PTS_ms': POINTS,
            'files': {p.name: sha(p) for p in assets.iterdir() if p.is_file()},
            'source_gif_note': 'Generated source cards on GIF 10 ms grid; use native NUT for exact 7 ms interval.'})
        record.update(status='passed', cli_calls=sum(call['command'][:len(prefix)] == list(map(str, prefix))
                      for call in record['calls']), native_commands=len(record['calls']),
                      assets={p.relative_to(ROOT).as_posix(): sha(p) for p in assets.iterdir() if p.is_file()})
    except BaseException as caught:
        record.update(status='failed', error={'type': type(caught).__name__, 'message': str(caught)})
        raise
    finally:
        record['frozen_after'] = frozen()
        record['frozen_equal'] = record['frozen_before'] == record['frozen_after']
        record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save()
        print(json.dumps({k: record.get(k) for k in ('status', 'cli_calls', 'native_commands', 'frozen_equal', 'error')}), flush=True)


if __name__ == '__main__':
    main()
