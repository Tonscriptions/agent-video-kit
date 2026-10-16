"""Publish actual archived/current CLI renders and independent source-clock gates.

Requires existing native Pillow/NumPy, FFmpeg, a local font and its license.
No network, model inference, installation, private footage or GUI is involved.
"""
from __future__ import annotations

import argparse
import array
import bisect
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '6ba099c72fea18913fda354769188fb4761e710f'
TPS, FPS, WIDTH, HEIGHT = 90000, 24, 512, 288


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def integral(local, pieces):
    # Independent closed-form fixture oracle; no product clock imports.
    total = 0.
    for left, right, speed_left, speed_right in pieces:
        span = right - left
        portion = max(0., min(local, right) - left)
        slope = (speed_right - speed_left) / span
        total += portion / speed_left if abs(slope) < 1e-12 else math.log1p(slope * portion / speed_left) / slope
    return total


def forward(step, source):
    span = step['out'] - step['in']
    elapsed = integral(source - step['in'], step['pieces'])
    elapsed *= step['duration'] / integral(span, step['pieces'])
    return step['start'] + (step['duration'] - elapsed if step['reverse'] else elapsed)


def inverse(step, output):
    elapsed = output - step['start']
    if step['reverse']:
        elapsed = step['duration'] - elapsed
    elapsed *= integral(step['out'] - step['in'], step['pieces']) / step['duration']
    source = step['in']
    for left, right, speed_left, speed_right in step['pieces']:
        duration = integral(right - left, [(0., right - left, speed_left, speed_right)])
        if elapsed > duration + 1e-10:
            elapsed -= duration
            continue
        slope = (speed_right - speed_left) / (right - left)
        offset = elapsed * speed_left if abs(slope) < 1e-12 else speed_left * math.expm1(slope * elapsed) / slope
        return source + left + offset
    return step['out']


def run(output, work, font, license_file):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont, ImageSequence

    if output.exists() or work.exists():
        raise ValueError('Use fresh output/work directories; existing evidence is never overwritten')
    if not font.is_file() or not license_file.is_file():
        raise ValueError('Supply an existing local font and its actual license')
    output.mkdir(parents=True)
    work.mkdir(parents=True)
    baseline = work / 'baseline'
    archive = subprocess.run(['git', '-c', 'core.autocrlf=false', 'archive', '--format=zip', BASELINE,
                              'product/src', 'docs/specs/agent-project.schema.json'], cwd=ROOT, capture_output=True, check=True).stdout
    baseline_hashes = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        for entry in package.infolist():
            if entry.is_dir():
                continue
            target = (baseline / entry.filename).resolve()
            if not target.is_relative_to(baseline.resolve()):
                raise ValueError('Unexpected archive path')
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = package.read(entry)
            target.write_bytes(raw)
            baseline_hashes[entry.filename] = 'sha256:' + hashlib.sha256(raw).hexdigest()
    source_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT / 'product/src').rglob('*.py'))}
    project = work / 'project'
    calls = []
    bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'

    def cli(*args, old=False):
        started = time.monotonic()
        result = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', '-c', bootstrap,
                                 str(baseline / 'product/src' if old else ROOT / 'product/src'), *map(str, args)],
                                cwd=ROOT, capture_output=True, timeout=300)
        value = json.loads(result.stdout.decode('utf-8-sig'))
        calls.append({'argv': list(map(str, args)), 'baseline': old, 'exit_code': result.returncode,
                      'seconds': time.monotonic() - started, 'result': value})
        save(work / 'partial-calls.json', calls)
        if result.returncode:
            raise RuntimeError(value)
        return value

    def ffmpeg(args, data=None):
        result = subprocess.run(['ffmpeg', '-v', 'error', *args], input=data, capture_output=True, timeout=300)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', 'replace'))
        return result.stdout

    def decode(path, width=WIDTH, height=HEIGHT):
        return np.frombuffer(ffmpeg(['-i', str(path), '-map', '0:v:0', '-an', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1']),
                             np.uint8).reshape(-1, height, width, 3)

    def encode(path, frames, width=WIDTH, height=HEIGHT):
        ffmpeg(['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', str(FPS), '-i', 'pipe:0',
                '-an', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', str(path)], np.stack(frames).tobytes())

    font_large = ImageFont.truetype(str(font), 38)
    font_small = ImageFont.truetype(str(font), 17)
    originals = []
    for frame in range(72):
        image = Image.new('RGB', (WIDTH, HEIGHT), '#18506e')
        draw = ImageDraw.Draw(image)
        for x in range(0, WIDTH, 32):
            draw.line((x, 92, x, HEIGHT), fill='#296780')
        for bit in range(7):
            level = 240 if frame & (1 << bit) else 16
            draw.rectangle((32 + bit * 64, 24, 87 + bit * 64, 79), fill=(level,) * 3)
        draw.text((32, 106), f'SOURCE FRAME {frame:02d}', font=font_large, fill='#fff4c8')
        draw.text((34, 162), f'{frame / FPS:.3f} s | 24 fps | authored CC0', font=font_small, fill='white')
        x = 24 + round(frame / 71 * 440)
        draw.rectangle((x, 218, x + 24, 252), fill='#48dfb5')
        originals.append(np.asarray(image).copy())
    encode(output / 'source.mp4', originals)
    samples = array.array('h')
    for index in range(3 * 48000):
        at = index / 48000
        amplitude = .6 if .6 <= at < .9 or 1.8 <= at < 2.1 else .03
        value = round(32767 * amplitude * math.sin(2 * math.pi * 400 * at))
        samples.extend((value, value))
    with wave.open(str(output / 'pulses.wav'), 'wb') as handle:
        handle.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
        handle.writeframes(samples.tobytes())
    shutil.copyfile(license_file, output / 'font-license.txt')
    save(output / 'fixture-provenance.json', {
        'generated_by': 'scripts/smoke_nested_time_mapping.py', 'synthetic_media_license_spdx': 'CC0-1.0',
        'third_party_natural_media': False, 'model_inference': False,
        'font': {'name': font.name, 'sha256': sha(font), 'license_id': 'LicenseRef-DejaVu-Fonts',
                 'license_sha256': sha(license_file), 'font_binary_distributed': False},
        'inputs': {name: sha(output / name) for name in ['source.mp4', 'pulses.wav', 'font-license.txt']},
    })
    cli('project', 'init', project, '--name', 'Nested source-clock verification')
    for asset, name in [('frames', 'source.mp4'), ('pulses', 'pulses.wav')]:
        cli('media', 'ingest', '--project', project, '--input', output / name, '--asset-id', asset,
            '--source-url', 'local://authored-nested-clock', '--license-spdx', 'CC0-1.0',
            '--verification-status', 'verified', '--permitted-use', 'commercial_ad', '--evidence', output / 'fixture-provenance.json')
    value = json.loads((project / 'project.json').read_text(encoding='utf-8-sig'))
    value['settings']['canvas'].update(width=WIDTH, height=HEIGHT)
    value['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
    save(project / 'project.json', value)
    scenarios = {
        'forward': [{'speeds': (1., 4.)}],
        'reverse': [{'speeds': (1., 4.), 'reverse': True}],
        'compound': [{'speeds': (1., 3.), 'reverse': True}, {'speeds': (.7, 1.8), 'reverse': True}],
        'animated': [{'speeds': (1., 4.)}],
        'segments': [{'points': [(0., 1., 'hold'), (.75, 2., 'linear'), (2., 4., 'linear'), (3., 1., 'linear')]}],
    }
    timeline_specs = {}
    decoded = {}
    measures = {}
    authored_freeze = {}

    def authored_hashes():
        value = json.loads((project / 'project.json').read_text(encoding='utf-8-sig'))
        return {
            'authored_project': 'sha256:' + hashlib.sha256(json.dumps(
                {key: value[key] for key in ['assets', 'settings', 'sequences']},
                ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest(),
            'rights_ledger': sha(project / 'rights-ledger.json'),
        }

    def frame_identity(frame, animated):
        if animated:
            columns = np.flatnonzero(frame[HEIGHT // 2, :, 1] > 35)
            if not len(columns):
                raise AssertionError('Animated layer is absent')
            width = int(columns[-1] - columns[0] + 1)
            left = (WIDTH - width) / 2
            top = (HEIGHT - round(HEIGHT * width / WIDTH)) / 2
            positions = [(round(left + (60 + bit * 64) * width / WIDTH), round(top + 52 * width / WIDTH)) for bit in range(7)]
        else:
            width = WIDTH
            positions = [(60 + bit * 64, 52) for bit in range(7)]
        identity = sum(1 << bit for bit, (x, y) in enumerate(positions) if frame[y, x, 0] > 128)
        return identity, width

    for scenario, parents in scenarios.items():
        current = f'{scenario}_leaf'
        leaf_duration = 3 * TPS
        operations = [{'op': 'add_sequence', 'id': current, 'duration_tick': leaf_duration}]
        leaf = {'op': 'append_clip', 'sequence_id': current, 'track_id': current + '_video_1', 'id': scenario + '_video',
                'asset_id': 'frames', 'source_in_tick': 0, 'source_out_tick': leaf_duration, 'duration_tick': leaf_duration}
        if scenario == 'animated':
            leaf.update(transform={'scale': .4}, keyframes=[{'property': 'transform.scale', 'keyframes': [
                {'at_tick': 0, 'value': .4, 'interpolation': 'linear'}, {'at_tick': leaf_duration, 'value': .9, 'interpolation': 'linear'}]}])
        operations += [leaf, {'op': 'add_track', 'sequence_id': current, 'track_id': current + '_audio', 'kind': 'audio', 'order': 1},
                       {**leaf, 'id': scenario + '_audio', 'track_id': current + '_audio', 'asset_id': 'pulses'}]
        duration = leaf_duration
        steps = []
        for level, config in enumerate(parents):
            target = 'seq_main' if level == len(parents) - 1 else f'{scenario}_parent_{level}'
            span = duration / TPS
            points = config.get('points', [(0., config.get('speeds', (1., 1.))[0], 'linear'),
                                           (span, config.get('speeds', (1., 1.))[1], 'linear')])
            pieces = [(a[0], b[0], a[1], a[1] if a[2] == 'hold' else b[1]) for a, b in zip(points, points[1:])]
            output_duration = round(integral(span, pieces) * TPS)
            if target != 'seq_main':
                operations.append({'op': 'add_sequence', 'id': target, 'duration_tick': output_duration})
            steps.append({'in': 0., 'out': span, 'start': 0., 'duration': output_duration / TPS,
                          'reverse': bool(config.get('reverse')), 'pieces': pieces})
            operations.append({'op': 'append_sequence_clip', 'sequence_id': target,
                               'track_id': 'track_video_1' if target == 'seq_main' else target + '_video_1',
                               'nested_sequence_id': current, 'id': scenario + f'_container_{level}',
                               'source_in_tick': 0, 'source_out_tick': duration, 'duration_tick': output_duration,
                               'reverse': bool(config.get('reverse')), 'speed_curve': {'keyframes': [
                                   {'at_tick': round(at * TPS), 'speed': speed, 'interpolation': interpolation} for at, speed, interpolation in points]}})
            current, duration = target, output_duration
        value = json.loads((project / 'project.json').read_text(encoding='utf-8-sig'))
        value['sequences'][0]['tracks'][0]['clips'] = []
        value['sequences'][0]['duration_tick'] = duration
        save(project / 'project.json', value)
        change = work / f'{scenario}-changes.json'
        save(change, {'operations': operations})
        cli('timeline', 'compose', '--project', project, '--input', change)
        timeline_specs[scenario] = {'operations': operations, 'oracle_steps': steps, 'duration_tick': duration}
        preserved = authored_hashes()
        cli('validate', '--project', project, '--strict-rights')
        is_reversed = sum(step['reverse'] for step in steps) % 2
        candidates = []
        for frame in range(72):
            clock = (frame + is_reversed) / FPS
            for step in steps:
                clock = forward(step, clock)
            candidates.append((clock, frame))
        candidates.sort()
        for old in [True, False]:
            label = 'before' if old else 'after'
            actual = project / 'renders' / f'{label}-{scenario}.mp4'
            cli('render', '--project', project, '--output', actual, '--publish', old=old)
            target = output / actual.name
            shutil.copyfile(actual, target)
            shutil.copyfile(actual.with_suffix('.mp4.manifest.json'), target.with_suffix('.mp4.manifest.json'))
            frames = decode(target)
            decoded[label + '-' + scenario] = frames
            rows = []
            for index, frame in enumerate(frames):
                observed, width = frame_identity(frame, scenario == 'animated')
                position = max(0, bisect.bisect_right([item[0] for item in candidates], index / FPS + 2e-5) - 1)
                expected = candidates[position][1]
                record = {'frame': index, 'seconds': index / FPS, 'observed_source_frame': observed,
                          'expected_source_frame': expected, 'source_frame_error': abs(observed - expected)}
                if scenario == 'animated':
                    child = index / FPS
                    for step in reversed(steps):
                        child = inverse(step, child)
                    expected_width = WIDTH * (.4 + .5 * max(0., min(1., child / 3)))
                    record.update(observed_width=width, expected_width=expected_width, width_error=abs(width - expected_width))
                rows.append(record)
            pcm = np.frombuffer(ffmpeg(['-i', str(target), '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '48000',
                                       '-f', 'f32le', 'pipe:1']), np.float32)
            audio_rows = []
            for offset in range(0, len(pcm) - 960, 960):
                at = (offset + 480) / 48000
                if at >= duration / TPS:
                    continue
                source = at
                for step in reversed(steps):
                    source = inverse(step, source)
                if min(abs(source - edge) for edge in (.6, .9, 1.8, 2.1)) < .10:
                    continue
                expected = .6 <= source < .9 or 1.8 <= source < 2.1
                rms = float(np.sqrt(np.mean(pcm[offset:offset + 960].astype(np.float64) ** 2)))
                audio_rows.append({'seconds': at, 'source_seconds': source, 'rms': rms, 'expected_loud': expected,
                                   'observed_loud': rms > .15, 'matches': (rms > .15) == expected})
            measure = {'rows': rows, 'max_source_frame_error': max(row['source_frame_error'] for row in rows),
                       'source_frame_gate': 1, 'audio_rows': audio_rows,
                       'audio_mismatch_count': sum(not row['matches'] for row in audio_rows),
                       'audio_boundary_exclusion_source_seconds': .10, 'audio_rms_gate': .15,
                       'continuous_playback_reviewed': False, 'audio_listened': False}
            if scenario == 'animated':
                measure['max_width_error'] = max(row['width_error'] for row in rows)
                measure['width_gate_pixels'] = 3.
            measures[label + '-' + scenario] = measure
            if not old:
                assert measure['max_source_frame_error'] <= 1, (scenario, measure['max_source_frame_error'])
                assert measure['audio_mismatch_count'] == 0, (scenario, measure['audio_mismatch_count'])
                if scenario == 'animated':
                    assert measure['max_width_error'] <= 3., measure['max_width_error']
        after_hashes = authored_hashes()
        assert preserved == after_hashes
        authored_freeze[scenario] = {'before': preserved, 'after': after_hashes,
                                    'scope': 'assets/settings/sequences canonical JSON and raw Rights Ledger; render output registration/provenance is expected'}
    save(output / 'authored-timelines.json', timeline_specs)

    # Preview the real forward renders, including measured frame identities.
    # The source panel shows only the corresponding prefix of the 3 s input.
    preview_count = min(len(decoded['before-forward']), len(decoded['after-forward']))
    previews = []
    source_frames = decode(output / 'source.mp4')
    font_preview = ImageFont.truetype(str(font), 14)
    for index in range(preview_count):
        montage = Image.new('RGB', (960, 244), '#101c29')
        draw = ImageDraw.Draw(montage)
        for column, (title, frame) in enumerate([
            ('ORIGINAL: 3 s input, prefix shown', source_frames[index]),
            ('BEFORE: averaged leaf speed', decoded['before-forward'][index]),
            ('AFTER: composed source clock', decoded['after-forward'][index]),
        ]):
            montage.paste(Image.fromarray(frame).resize((320, 180)), (column * 320, 28))
            draw.text((column * 320 + 8, 6), title, font=font_preview, fill='white')
            if column:
                label = 'before' if column == 1 else 'after'
                row = measures[label + '-forward']['rows'][index]
                text = f'frame {row["observed_source_frame"]:02d}, expected {row["expected_source_frame"]:02d}, error {row["source_frame_error"]}'
                draw.text((column * 320 + 8, 218), text, font=font_preview,
                          fill='#ff9f87' if row['source_frame_error'] > 1 else '#62e3b4')
            else:
                draw.text((8, 218), f'output clock {index / FPS:.3f} s', font=font_preview, fill='white')
        previews.append(np.asarray(montage).copy())
    encode(output / 'nested-time-comparison.mp4', previews, 960, 244)
    gifs = [Image.fromarray(frame) for frame in previews]
    durations = [round((index + 1) * 100 / FPS) * 10 - round(index * 100 / FPS) * 10 for index in range(preview_count)]
    gifs[0].save(output / 'nested-time-comparison.gif', save_all=True, append_images=gifs[1:], duration=durations, loop=0, optimize=False)
    for index in sorted({0, preview_count // 2, preview_count - 1}):
        Image.fromarray(previews[index]).save(output / f'contact-frame-{index:02d}.png')
    probes = {}
    for path in sorted(output.glob('*.mp4')):
        probes[path.name] = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format',
                                                      '-of', 'json', str(path)], capture_output=True, check=True).stdout)
    with Image.open(output / 'nested-time-comparison.gif') as image:
        gif_durations = [frame.info['duration'] for frame in ImageSequence.Iterator(image)]
    assert all(sha(ROOT / name) == digest for name, digest in source_hashes.items())
    save(output / 'evidence.json', {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'baseline_ref': BASELINE,
        'baseline_executed_file_sha256': baseline_hashes, 'current_source_sha256': source_hashes,
        'script_sha256': sha(Path(__file__)), 'cli_calls': calls, 'scenarios': measures, 'probes': probes,
        'authored_project_freeze': authored_freeze,
        'preview': {'source_scope': f'first {preview_count} frames of the 72-frame authored source',
                    'actual_output_frames': preview_count, 'gif_frames': len(gif_durations),
                    'gif_durations_ms': gif_durations, 'gif_total_ms': sum(gif_durations),
                    'mp4_fps': FPS, 'mp4_duration_seconds': preview_count / FPS,
                    'continuous_playback_reviewed': False, 'audio_listened': False, 'montage_has_audio': False},
        'new_model_inferences': 0, 'private_media_published': False, 'full_jianying_parity_accepted': False,
        'limitations': ['Source-frame gate is 1 CFR source frame, not VFR timestamp equivalence',
                        'Audio envelope gate excludes .10 source seconds around pulse boundaries; no phase or listening acceptance',
                        'No nested freeze/caption-cue, parent-pivot/mask-space, nonlinear speed easing, performance or complete parity acceptance'],
        'file_sha256': {path.name: sha(path) for path in sorted(output.iterdir()) if path.is_file()},
    })
    print(json.dumps({'cli_calls': len(calls), 'scenarios': {
        name: {'source_frame_error': value['max_source_frame_error'], 'audio_mismatches': value['audio_mismatch_count'],
               'max_width_error': value.get('max_width_error')} for name, value in measures.items()},
        'preview_frames': preview_count, 'gif_total_ms': sum(gif_durations)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--font-file', type=Path, required=True)
    parser.add_argument('--font-license-file', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir.resolve(), args.work_dir.resolve(), args.font_file.resolve(), args.font_license_file.resolve())
