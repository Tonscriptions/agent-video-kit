"""Actual local CLI camera coverage, complete lossless frames/PCM, MP4 and GIF."""
from __future__ import annotations
import argparse
from array import array
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
from PIL import Image, ImageDraw
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
W, H, TPS = 320, 180, 90000


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'evidence', 'assets'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    work, evidence, assets = (getattr(args, name).resolve() for name in ('work', 'evidence', 'assets'))
    assert work.is_relative_to(ROOT / 'product/.runtime')
    assert evidence.is_relative_to(ROOT / 'docs/validation') and assets.is_relative_to(ROOT / 'docs/assets')
    assert not any(path.exists() for path in (work, evidence, assets))
    for path in (work, evidence, assets):
        path.mkdir(parents=True)
    (evidence / 'executed-smoke.py.txt').write_bytes(Path(__file__).read_bytes())
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'native_windows': sys.platform == 'win32', 'virtualization': False, 'network': False,
        'frozen_before': frozen(), 'calls': [], 'checks': [], 'media': {},
        'continuous_playback_reviewed': False, 'audio_listened': False, 'full_capcut_parity': False}
    def save(): write(evidence / 'verification.json', record)
    def check(name, condition, **details):
        record['checks'].append({'name': name, 'ok': bool(condition), **details})
        save()
        assert condition, name
    temp = ROOT / 'product/.runtime/temp'
    temp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp), PYTHONDONTWRITEBYTECODE='1')
    bootstrap = ('import sys;sys.path.insert(0,sys.argv.pop(1));'
        'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
        'from ai_ad_editor.cli import main;raise SystemExit(main())')
    prefix = ([sys.executable, '-I', '-S', '-B', '-X', 'utf8', args.installed.resolve() / 'run.py'] if args.installed else
              [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap, ROOT / 'product/src'])
    prefix = list(map(str, prefix))
    def run(label, command, data=None, expected=0, binary=False, cli=False):
        command = list(map(str, command))
        started = time.monotonic()
        result = subprocess.run(command, input=data, capture_output=True, cwd=ROOT, env=env, timeout=600)
        (evidence / (label + '.stderr.log')).write_bytes(result.stderr)
        digest = 'sha256:' + hashlib.sha256(result.stdout).hexdigest()
        if binary:
            write(evidence / (label + '.stdout-summary.json'), {'bytes': len(result.stdout), 'sha256': digest})
        else:
            (evidence / (label + '.stdout.log')).write_bytes(result.stdout)
        record['calls'].append({'label': label, 'command': command, 'exit_code': result.returncode,
            'expected_exit_code': expected, 'wall_seconds': time.monotonic() - started,
            'stdout_sha256': digest, 'cli': cli})
        save()
        assert result.returncode == expected, label + ': ' + (result.stderr + result.stdout)[-1600:].decode('utf8', 'replace')
        return result.stdout
    def cli(label, *argv, expected=0):
        return json.loads(run(label, [*prefix, *argv], expected=expected, cli=True))
    exe, probe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    assert exe and probe
    record.update(ffmpeg={'path': exe, 'sha256': sha(exe)}, ffprobe={'path': probe, 'sha256': sha(probe)})
    def video(label, path):
        return run(label, [exe, '-v', 'error', '-i', path, '-map', '0:v:0', '-an', '-fps_mode', 'passthrough',
            '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1'], binary=True)
    def audio(label, path):
        return run(label, [exe, '-v', 'error', '-i', path, '-map', '0:a:0', '-vn', '-ar', '48000', '-ac', '2',
            '-f', 'f32le', '-c:a', 'pcm_f32le', 'pipe:1'], binary=True)
    def gif(path, raw):
        size = W * H * 4
        assert len(raw) % size == 0
        frames = [Image.frombytes('RGBA', (W, H), raw[index:index + size]).convert('RGB') for index in range(0, len(raw), size)]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=40, loop=0, disposal=2, optimize=False)
        with Image.open(path) as image:
            total = 0
            for index in range(image.n_frames):
                image.seek(index)
                total += image.info.get('duration', 0)
            return {'frames': image.n_frames, 'duration_ms': total, 'actual_mp4_decode': path.stem in ('trim', 'stretch')}
    try:
        cards = []
        for index in range(50):
            image = Image.new('RGBA', (W, H), (30 + index * 3, 50 + index * 2, 220 - index * 3, 255))
            draw = ImageDraw.Draw(image)
            draw.rectangle((14, 32, 306, 126), fill=(12, 18, 29, 255))
            draw.text((24, 45), 'ORIGINAL LOCAL CAMERA / 25 FPS', fill='white')
            draw.text((24, 72), f'EVENT {index:02d} / {index * 40:04d} ms', fill='white')
            draw.text((24, 98), 'CAMERA B COVERS 400..1840 ms', fill='white')
            cards.append(image)
        raw = b''.join(image.tobytes() for image in cards)
        rng = random.Random(61243)
        gains = [.1 + .75 * rng.random() for _ in range(100)]
        pcm = array('f')
        for sample in range(96000):
            gain = gains[sample // 960]
            pcm.extend((gain * math.sin(2 * math.pi * 433 * sample / 48000), gain * math.sin(2 * math.pi * 739 * sample / 48000)))
        raw_audio = work / 'original.f32le'
        raw_audio.write_bytes(pcm.tobytes())
        reference = assets / 'source-reference.mkv'
        camera = assets / 'source-camera.mkv'
        run('generate-reference', [exe, '-v', 'error', '-filter_threads', '1', '-f', 'rawvideo', '-pixel_format', 'rgba',
            '-video_size', f'{W}x{H}', '-framerate', '25', '-i', 'pipe:0', '-f', 'f32le', '-ar', '48000', '-ac', '2', '-i', raw_audio,
            '-map', '0:v', '-map', '1:a', '-c:v', 'ffv1', '-pix_fmt', 'bgra', '-c:a', 'pcm_f32le', reference], raw)
        run('generate-camera', [exe, '-v', 'error', '-filter_complex_threads', '1', '-i', reference, '-filter_complex',
            '[0:v]trim=start_frame=10:end_frame=46,setpts=PTS-STARTPTS[v];[0:a]atrim=start_sample=19200:end_sample=88320,asetpts=PTS-STARTPTS[a]',
            '-map', '[v]', '-map', '[a]', '-c:v', 'ffv1', '-pix_fmt', 'bgra', '-c:a', 'pcm_f32le', camera])
        check('all-generated-reference-RGBA', video('decode-reference', reference) == raw, frames=50, bytes=len(raw))
        check('all-generated-camera-RGBA', video('decode-camera', camera) == b''.join(image.tobytes() for image in cards[10:46]), frames=36)
        check('all-generated-reference-PCM', audio('decode-reference-pcm', reference) == pcm.tobytes(), bytes=len(pcm.tobytes()))
        project = work / 'project'
        discovery = cli('capabilities', 'capabilities')['data']
        check('coverage-policy-discoverable', 'multicam_source_coverage' in json.dumps(discovery))
        cli('project-init', 'project', 'init', project)
        for asset_id, path in (('reference', reference), ('camera', camera)):
            cli('ingest-' + asset_id, 'media', 'ingest', '--project', project, '--input', path, '--asset-id', asset_id,
                '--source-url', 'local://multicam-source-range/original', '--license-spdx', 'CC0-1.0',
                '--license-url', 'local://multicam-source-range/CC0-1.0', '--verification-status', 'verified',
                '--permitted-use', 'commercial_ad', '--creator', 'agent-video-kit', '--evidence', 'Original generated event cards and synthesized stereo tones')
        p = json.loads((project / 'project.json').read_bytes())
        p['settings']['canvas'] = {'width': W, 'height': H, 'background': '#000000'}
        p['settings']['timebase'] = {'ticks_per_second': TPS, 'display_fps': {'num': 25, 'den': 1}}
        write(project / 'project.json', p)
        request = project / 'master-audio.json'
        write(request, {'operations': [{'op': 'append_clip', 'track_id': 'track_audio_1', 'id': 'master_audio',
            'asset_id': 'reference', 'timeline_start_tick': 0, 'duration_tick': 180000, 'source_in_tick': 0, 'source_out_tick': 180000},
            {'op': 'set_sequence_duration', 'sequence_id': 'seq_main', 'duration_tick': 180000, 'trim': False}]})
        cli('compose-explicit-master-audio', 'timeline', 'compose', '--project', project, '--input', request)
        plan = project / 'switch-plan.json'
        rows = [{'start_seconds': 0., 'end_seconds': 2., 'camera_asset_id': 'camera'}]
        write(plan, rows)
        common = ('media', 'multicam', '--project', project, '--source-asset-id', 'reference', '--source-asset-id', 'camera',
            '--reference-asset-id', 'reference', '--sample-rate', '8000', '--analysis-seconds', '2', '--max-offset-seconds', '.6',
            '--switch-plan', plan, '--start-seconds', '0', '--end-seconds', '2', '--track-id', 'track_video_1', '--output', project / 'validation/coverage.json')
        before = (project / 'project.json').read_bytes()
        history = sorted(path.name for path in (project / 'history').glob('*.json'))
        for label, options in (('default-dry-refusal', ('--dry-run',)), ('default-apply-refusal', ('--apply', '--replace-track'))):
            value = cli(label, *common, *options, expected=2)
            check(label + '-explicit-shortfall', value['errors'][0]['code'] == 'MULTICAM_SOURCE_SHORTFALL')
            check(label + '-no-author-report-snapshot-write', (project / 'project.json').read_bytes() == before
                and not (project / 'validation/coverage.json').exists()
                and sorted(path.name for path in (project / 'history').glob('*.json')) == history)
        dry = cli('trim-array-dry', *common, '--source-shortfall', 'trim', '--dry-run')['data']['plan']
        write(plan, {'segments': rows})
        wrapped = cli('trim-object-dry', *common, '--source-shortfall', 'trim', '--dry-run')['data']['plan']
        fields = ('start_seconds', 'end_seconds', 'timeline_start_tick', 'duration_tick', 'source_in_tick', 'source_out_tick', 'speed')
        check('array-and-object-plan-equivalence', {k: dry['segments'][0][k] for k in fields} == {k: wrapped['segments'][0][k] for k in fields})
        check('trim-dry-no-author-or-report-write', (project / 'project.json').read_bytes() == before and not (project / 'validation/coverage.json').exists())
        p = json.loads(before)
        p['sequences'][0]['tracks'][0]['locked'] = True
        write(project / 'project.json', p)
        locked = cli('locked-apply-dry-refusal', *common, '--source-shortfall', 'trim', '--apply', '--dry-run', expected=2)
        check('locked-target-refuses', locked['errors'][0]['code'] == 'TRACK_LOCKED')
        (project / 'project.json').write_bytes(before)
        applied = cli('trim-apply', *common, '--source-shortfall', 'trim', '--apply', '--replace-track')['data']['plan']
        row = applied['segments'][0]
        check('trim-unity-source-event-placement', tuple(row[k] for k in fields) == (.4, 1.84, 36000, 129600, 0, 129600, 1.))
        offset = next(row for row in applied['sync']['offsets'] if row['asset_id'] == 'camera')
        check('bounded-audio-offset-matches-generated-event-clock', offset['relative_delay_seconds'] == -.4, measured=offset)
        p = json.loads((project / 'project.json').read_bytes())
        check('requested-two-second-window-retained', p['sequences'][0]['duration_tick'] == 180000)
        preview = cli('trim-preview', 'preview', 'range', '--project', project, '--start-frame', '0', '--end-frame', '50', '--height', H)['data']
        master = Path(preview['master'])
        shutil.copy2(master, assets / 'trim-lossless.nut')
        expected = bytes((0, 0, 0, 255)) * (W * H * 10) + b''.join(image.tobytes() for image in cards[10:46]) + bytes((0, 0, 0, 255)) * (W * H * 4)
        check('trim-all-lossless-event-frames-and-both-gaps', video('decode-trim-lossless', master) == expected,
              frames=50, bytes=len(expected), max_RGBA_error=0)
        check('trim-complete-explicit-master-PCM', audio('decode-trim-lossless-pcm', master) == pcm.tobytes(), bytes=len(pcm.tobytes()), samples_per_channel=96000)
        for label, options in (('trim', None), ('stretch', ('--source-shortfall', 'stretch', '--apply', '--replace-track'))):
            if options:
                stretched = cli('stretch-apply', *common, *options)['data']['plan']
                check('explicit-stretch-warns-clock-change', any(v['code'] == 'MULTICAM_SOURCE_CLOCK_CHANGED' for v in stretched['warnings'])
                    and stretched['segments'][0]['speed'] == .72)
            output = project / 'renders' / (label + '.mp4')
            rendered = cli(label + '-render', 'render', '--project', project, '--output', output, '--profile', 'custom',
                '--width', W, '--height', H, '--crf', '0', '--pixel-format', 'yuv444p')['data']
            shutil.copy2(Path(rendered['manifest']), evidence / (label + '-render-manifest.json'))
            shutil.copy2(output, assets / (label + '.mp4'))
            encoded = video(label + '-decode-encoded', output)
            size = W * H * 4
            check(label + '-encoded-frame-count', len(encoded) == size * 50, frames=50)
            if label == 'trim':
                expected_ids = [-1] * 10 + list(range(10, 46)) + [-1] * 4
                actual_patches = [tuple(encoded[index * size:index * size + 3]) for index in range(50)]
                wanted = [(0, 0, 0) if index < 0 else (30 + index * 3, 50 + index * 2, 220 - index * 3) for index in expected_ids]
                error = max(abs(a - b) for got, target in zip(actual_patches, wanted) for a, b in zip(got, target))
                check('trim-encoded-event-identity-patches', error <= 2, observed_max_rgb_error=error, whole_encoded_RGBA_equality_claimed=False)
                sheet = Image.new('RGB', (W * 4, H * 2))
                for cell, index in enumerate((0, 9, 10, 20, 25, 45, 46, 49)):
                    sheet.paste(Image.frombytes('RGBA', (W, H), encoded[index * size:(index + 1) * size]).convert('RGB'), ((cell % 4) * W, (cell // 4) * H))
                sheet.save(assets / 'trim-event-boundaries.png')
            else:
                first = tuple(encoded[:3])
                check('explicit-stretch-visibly-replaces-first-gap', max(abs(a - b) for a, b in zip(first, (60, 70, 190))) <= 2)
            observed = json.loads(run(label + '-encoded-PTS', [probe, '-v', 'error', '-select_streams', 'v:0', '-show_frames', '-show_streams',
                '-show_entries', 'frame=pts,duration:stream=time_base', '-of', 'json', output]))
            base = Fraction(observed['streams'][0]['time_base'])
            pts = [int(frame['pts']) * base for frame in observed['frames']]
            check(label + '-all-encoded-PTS', pts == [Fraction(index, 25) for index in range(50)])
            record.setdefault('GIF', {})[label] = gif(assets / (label + '.gif'), encoded)
        record['GIF']['source-reference'] = gif(assets / 'source-reference.gif', raw)
        record['GIF']['source-camera'] = gif(assets / 'source-camera.gif', b''.join(image.tobytes() for image in cards[10:46]))
        write(assets / 'source-origin.json', {'license': 'CC0-1.0', 'creator': 'agent-video-kit', 'original_generated_media': True,
            'source_frames': 50, 'camera_frames': 36, 'fps': 25, 'camera_reference_bounds_seconds': [.4, 1.84],
            'generator_sha256': sha(__file__), 'continuous_playback_reviewed': False, 'audio_listened': False})
        record['media'] = {path.relative_to(ROOT).as_posix(): {'sha256': sha(path), 'bytes': path.stat().st_size}
                           for path in sorted(assets.iterdir()) if path.is_file()}
        record.update(status='passed', cases={'trim': {'reference_window_seconds': [0, 2], 'covered_event_seconds': [.4, 1.84],
            'speed': 1, 'leading_gap_frames': 10, 'trailing_gap_frames': 4, 'lossless_RGBA_bytes': len(expected), 'lossless_PCM_bytes': len(pcm.tobytes())},
            'stretch': {'speed': .72, 'event_sync_preserved': False}}, installed=bool(args.installed))
    except BaseException as error:
        record.update(status='failed', error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), frozen_after=frozen())
        record['frozen_equal'] = record['frozen_before'] == record['frozen_after']
        record['cli_calls'] = sum(bool(row['cli']) for row in record['calls'])
        record['native_commands'] = sum(not row['cli'] for row in record['calls'])
        save()
        print(json.dumps({k: record.get(k) for k in ('status', 'cli_calls', 'native_commands', 'frozen_equal', 'error')}), flush=True)
    assert record['frozen_equal']


if __name__ == '__main__':
    main()
