"""Real offline CLI delivery, independent alpha planes, PCM and drift controls."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
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

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
TPS, FPS, W, H, SR = 90000, 10, 256, 64, 48000
BASE = '409c207009b7e6bb484d01d550b64291d5b4d4df'


def digest(raw):
    return 'sha256:'+hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                    encoding='utf-8', newline='\n')


def run(public, work, evidence):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    for directory in (public, work, evidence):
        directory.mkdir(parents=True, exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    before = frozen()
    calls, cases, negatives, baseline_cases = [], [], [], []
    env = dict(os.environ)
    env.update(TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'),
               TMPDIR=str(ROOT/'product/.runtime/temp'), PYTHONDONTWRITEBYTECODE='1')
    bootstrap = ('import sys;sys.path.insert(0,sys.argv.pop(1));'
                 'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
                 'from ai_ad_editor.cli import main;raise SystemExit(main())')

    def cli(*args, expected=0, baseline=False):
        source = ROOT/('product/.runtime/delivery-precision-baseline-20261018/product/src' if baseline else 'product/src')
        command = [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap, str(source), *map(str, args)]
        start = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=360)
        index = len(calls)+1
        (evidence/f'{index:03}.stdout.json').write_bytes(result.stdout)
        (evidence/f'{index:03}.stderr.log').write_bytes(result.stderr)
        row = {'index': index, 'args': list(map(str, args)), 'baseline': baseline,
               'exit_code': result.returncode, 'expected_exit_code': expected,
               'seconds': time.monotonic()-start, 'stdout_sha256': digest(result.stdout),
               'stderr_sha256': digest(result.stderr)}
        calls.append(row)
        save(evidence/'calls.json', calls)
        value = json.loads(result.stdout.decode('utf-8-sig')) if result.stdout else {'stderr': result.stderr.decode('utf-8', 'replace')}
        print(json.dumps({'cli_call': index, 'command': list(map(str, args[:2])), 'baseline': baseline,
                          'exit_code': result.returncode}), flush=True)
        assert result.returncode == expected, (row, value)
        return value

    def native(*args, data=None):
        result = subprocess.run(['ffmpeg', '-v', 'error', '-y', *map(str, args)], input=data,
                                capture_output=True, timeout=180)
        assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')
        return result.stdout

    def rgba(path, width=W, height=H, decoder=None):
        options = ['-c:v', decoder] if decoder else []
        raw = native(*options, '-i', path, '-map', '0:v:0', '-an', '-fps_mode', 'passthrough',
                     '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1')
        return np.frombuffer(raw, dtype=np.uint8).reshape(-1, height, width, 4)

    def pcm(path):
        raw = native('-i', path, '-map', '0:a:0', '-vn', '-ar', SR, '-ac', 2, '-f', 'f32le', 'pipe:1')
        return np.frombuffer(raw, dtype='<f4').reshape(-1, 2)

    def author(project, sequences, width=W, height=H):
        payload = json.loads((project/'project.json').read_bytes())
        payload['settings']['canvas'].update(width=width, height=height)
        payload['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
        payload['sequences'] = copy.deepcopy(sequences)
        save(project/'project.json', payload)
        return payload

    def ingest(project, path, aid):
        return cli('media', 'ingest', '--project', project, '--input', path, '--asset-id', aid,
                   '--verification-status', 'verified', '--permitted-use', 'commercial_ad',
                   '--license-spdx', 'CC0-1.0', '--source-url', 'local://authored-delivery-precision',
                   '--evidence', 'local://procedural-fixture-generation')

    def clip(cid, aid, duration, **extra):
        return {'id': cid, 'asset_id': aid, 'timeline_start_tick': 0, 'duration_tick': duration,
                'source_in_tick': 0, 'source_out_tick': duration, **extra}

    def track(tid, kind, clips, order=0):
        return {'id': tid, 'kind': kind, 'order': order, 'clips': clips}

    def render(project, name, *, alpha=False, codec='libvpx-vp9', crf=0, baseline=False,
               mp4=False, expected=0):
        suffix = '.webm' if alpha else '.mp4' if mp4 else '.mkv'
        output = project/'renders'/(name+suffix)
        options = (['--container', 'webm', '--video-codec', codec, '--audio-codec', 'libopus',
                    '--pixel-format', 'yuva420p'] if alpha else [] if mp4 else
                   ['--container', 'mkv', '--audio-codec', 'pcm_f32le', '--pixel-format', 'yuv444p'])
        value = cli('render', '--project', project, '--output', output, '--crf', crf,
                    *options, '--publish', baseline=baseline, expected=expected)
        if expected:
            assert not output.exists()
            return output, value
        shutil.copyfile(output, public/output.name)
        manifest = Path(value['data']['manifest'])
        shutil.copyfile(manifest, evidence/(name+'.manifest.json'))
        return output, value

    def frame_clock(path, frames, rate=Fraction(FPS)):
        raw = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(path)])
        data = json.loads(raw)['frames']
        assert len(data) == frames, (path, len(data), frames)
        error = max(abs(float(row['best_effort_timestamp_time'])-float(Fraction(i, 1)/rate))
                    for i, row in enumerate(data))
        assert error <= .00051, (path, error)
        return error

    def record(name, path, result, *, width=W, height=H, decoder=None,
               expected_alpha=None, expected_pcm=None, expected_rgb=None, exact_alpha=False):
        picture, audio = rgba(path, width, height, decoder), pcm(path)
        assert np.isfinite(audio).all()
        row = {'name': name, 'path': path.name, 'width': width, 'height': height,
               'frames': len(picture), 'stereo_sample_frames': len(audio),
               'pts_max_error_seconds': frame_clock(path, len(picture)), 'output_sha256': sha(path),
               'decoded_rgba_sha256': digest(picture.tobytes()), 'decoded_pcm_sha256': digest(audio.tobytes()),
               'decoder': decoder, 'audio_content_accepted': expected_pcm is not None,
               'delivery': result['data']['delivery'], 'quality': result['data']['quality']}
        if expected_alpha is not None:
            assert picture[:, :, :, 3].shape == expected_alpha.shape
            delta = np.abs(picture[:, :, :, 3].astype(np.int16)-expected_alpha.astype(np.int16))
            row.update(max_alpha_error=int(delta.max()), mismatched_alpha_pixels=int(np.count_nonzero(delta)),
                       exact_alpha_gate_required=exact_alpha, threshold_max_alpha_error=0 if exact_alpha else None)
            if exact_alpha:
                assert not delta.any(), row
        if expected_pcm is not None:
            assert audio.shape == expected_pcm.shape
            row['max_pcm_error'] = float(np.abs(audio-expected_pcm).max())
            assert row['max_pcm_error'] <= 2e-6, row
        if expected_rgb is not None:
            assert picture[:, :, :, :3].shape == expected_rgb.shape
            row['max_rgb_error'] = float(np.abs(picture[:, :, :, :3].astype(float)-expected_rgb).max())
            assert row['max_rgb_error'] <= 3, row
        cases.append(row)
        save(public/(name+'-verification.json'), row)
        return picture, audio

    try:
        y, x = np.indices((H, W))
        source = np.empty((12, H, W, 4), dtype=np.uint8)
        for index in range(12):
            source[index, :, :, :3] = [60+7*index, 120, 210]
            source[index, :, :, 3] = (x+7*y+19*index) % 256
        video = public/'source-ramp.mkv'
        native('-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{W}x{H}', '-r', FPS,
               '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgra', video, data=source.tobytes())
        assert np.array_equal(rgba(video), source)
        n = np.arange(57600)/SR
        sound = np.stack((.09+.01*n, -.07+.005*n), axis=1).astype('<f4')
        wav = public/'source-audio.wav'
        native('-f', 'f32le', '-ar', SR, '-ac', 2, '-i', 'pipe:0', '-c:a', 'pcm_f32le',
               wav, data=sound.tobytes())
        alpha = np.concatenate((source[:5, :, :, 3], np.repeat(source[4:5, :, :, 3], 4, axis=0), source[5:, :, :, 3]))
        held_rgba = np.concatenate((source[:5], np.repeat(source[4:5], 4, axis=0), source[5:]))
        project = work/'alpha'
        cli('project', 'init', project)
        ingest(project, video, 'ramp')
        ingest(project, wav, 'sound')
        root_id = json.loads((project/'project.json').read_bytes())['sequences'][0]['id']
        child = {'id': 'delivery_child', 'name': 'local alpha and sound', 'duration_tick': 108000,
                 'tracks': [track('child_picture', 'video', [clip('leaf', 'ramp', 108000)]),
                            track('child_sound', 'audio', [clip('voice', 'sound', 108000)], 1)]}
        parent = {'id': root_id, 'name': 'completed child hold', 'duration_tick': 144000,
                  'tracks': [track('parent_picture', 'video', [{'id': 'compound', 'sequence_id': child['id'],
                    'timeline_start_tick': 0, 'source_in_tick': 0, 'source_out_tick': 108000,
                    'duration_tick': 144000, 'freeze': {'at_tick': 45000, 'duration_tick': 36000, 'audio_mode': 'silence'}}])]}
        author(project, [parent, child])
        cli('validate', '--project', project, '--strict-rights')
        cli('policy', 'audit', '--project', project)
        old, old_result = render(project, 'DP01-v51', alpha=True, baseline=True)
        old_picture = rgba(old, decoder='libvpx-vp9')
        old_delta = np.abs(old_picture[:, :, :, 3].astype(np.int16)-alpha)
        assert old_delta.any()
        baseline_cases.append({'name': 'DP01-v51', 'base_commit': BASE, 'frames': len(old_picture),
            'output_sha256': sha(old), 'max_alpha_error': int(old_delta.max()),
            'mismatched_alpha_pixels': int(np.count_nonzero(old_delta)), 'threshold_max_alpha_error': 0})
        first, result = render(project, 'DP01-vp9-freeze', alpha=True)
        actual, _ = record('DP01', first, result, decoder='libvpx-vp9', expected_alpha=alpha, exact_alpha=True)
        opaque, result = render(project, 'DP00-opaque-pcm')
        held_sound = np.concatenate((sound[:24000], np.zeros((19200, 2), dtype='<f4'), sound[24000:]))
        expected_black = held_rgba[:, :, :, :3].astype(float)*held_rgba[:, :, :, 3:4]/255
        record('DP00', opaque, result, expected_pcm=held_sound, expected_rgb=expected_black)
        package = public/'DP01-project.zip'
        cli('convert', 'export', '--project', project, '--target-format', 'package', '--output', package)

        restored = work/'reimport'
        cli('convert', 'import', '--input', package, '--output', restored)
        ingest(restored, first, 'vp9_roundtrip')
        direct = {'id': root_id, 'name': 'reimported transparent video', 'duration_tick': 144000,
                  'tracks': [track('readback', 'video', [clip('readback_clip', 'vp9_roundtrip', 144000)])]}
        author(restored, [direct])
        second, result = render(restored, 'DP02-vp9-roundtrip', alpha=True)
        second_rgba, _ = record('DP02', second, result, decoder='libvpx-vp9', expected_alpha=alpha, exact_alpha=True)
        cli('convert', 'export', '--project', restored, '--target-format', 'package', '--output', public/'DP02-project.zip')

        for number, background in ((3, 16), (4, 240)):
            image = public/f'background-{background}.png'
            Image.new('RGB', (W, H), (background,)*3).save(image)
            ingest(restored, image, f'background_{background}')
            composite = copy.deepcopy(direct)
            composite['tracks'][0]['order'] = 1
            composite['tracks'].insert(0, track('background', 'video', [clip('background_clip', f'background_{background}', 144000)]))
            author(restored, [composite])
            path, result = render(restored, f'DP0{number}-over-{background}')
            coverage = actual[:, :, :, 3:4].astype(float)/255
            expected = actual[:, :, :, :3]*coverage+background*(1-coverage)
            record(f'DP0{number}', path, result, expected_rgb=expected)

        lossy, result = render(project, 'DP05-lossy-vp9', alpha=True, crf=35)
        record('DP05', lossy, result, decoder='libvpx-vp9', expected_alpha=alpha)
        vp8, result = render(project, 'DP06-vp8', alpha=True, codec='libvpx', crf=10)
        vp8_rgba, _ = record('DP06', vp8, result, decoder='libvpx', expected_alpha=alpha)
        assert vp8_rgba[:, :, :, 3].min() < 5 and vp8_rgba[:, :, :, 3].max() > 250
        ingest(restored, vp8, 'vp8_roundtrip')
        vp8_direct = copy.deepcopy(direct)
        vp8_direct['tracks'][0]['clips'][0]['asset_id'] = 'vp8_roundtrip'
        author(restored, [vp8_direct])
        path, result = render(restored, 'DP07-vp8-roundtrip', alpha=True)
        record('DP07', path, result, decoder='libvpx-vp9', expected_alpha=vp8_rgba[:, :, :, 3], exact_alpha=True)

        # Further delivery/control cases follow below; any failure retains the
        # actual outputs, raw CLI envelopes and source fingerprints.
        finish(public, work, evidence, cli, native, render, record, rgba, pcm, frame_clock,
               calls, cases, negatives, baseline_cases, before, held_rgba, old_picture, actual)
    except BaseException as exc:
        save(evidence/'failure.json', {'error': repr(exc), 'calls': calls, 'frozen_before': before,
                                     'frozen_after': frozen(), 'partials_preserved': True})
        save(public/'STATUS.json', {'status': 'failed_partial_run', 'error': repr(exc),
                                   'not_a_complete_release': True})
        raise


def finish(public, work, evidence, cli, native, render, record, rgba, pcm, frame_clock,
           calls, cases, negatives, baseline_cases, before, held_rgba, old_picture, actual):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    previous = ROOT/'docs/assets/nested-freeze-v51-final-20261018'
    fractional = work/'fractional'
    cli('convert', 'import', '--input', previous/'NF06-project.zip', '--output', fractional)
    payload = json.loads((fractional/'project.json').read_bytes())
    sequence = payload['sequences'][0]
    sequence['duration_tick'] = 360900
    save(fractional/'project.json', payload)
    sequence_id = sequence['id']
    width, height = payload['settings']['canvas']['width'], payload['settings']['canvas']['height']
    cli('validate', '--project', fractional, '--strict-rights')
    failed_path, failed = render(fractional, 'DP09-v51-failed', baseline=True, mp4=True, expected=6)
    assert 'OUTPUT_AV_SYNC_OUT_OF_RANGE' in json.dumps(failed)
    baseline_cases.append({'name': 'DP09-v51-failed', 'base_commit': BASE,
                           'exit_code': 6, 'output_published': failed_path.exists(), 'result': failed})
    reference_path = previous/'fractional-root-control.mkv'
    reference_rgb, reference_pcm = rgba(reference_path, width, height), pcm(reference_path)
    path, result = render(fractional, 'DP08-fractional-pcm')
    new_rgba, new_pcm = record('DP08', path, result, width=width, height=height,
                               expected_rgb=reference_rgb[:, :, :, :3], expected_pcm=reference_pcm)
    assert np.array_equal(new_rgba[:, :, :, :3], reference_rgb[:, :, :, :3])
    assert np.array_equal(new_pcm, reference_pcm) and len(new_pcm) == 192480
    cases[-1]['reference_scope'] = 'fixed-V51-opaque-RGB-PCM-compatibility; not-independent-original-audio-quality'
    save(public/'DP08-verification.json', cases[-1])
    mp4, result = render(fractional, 'DP09-fractional-mp4', mp4=True)
    mp4_rgba, mp4_pcm = record('DP09', mp4, result, width=width, height=height)
    assert len(mp4_rgba) == 41
    metrics = result['data']['quality']['metrics']
    assert abs(metrics['av_duration_delta_seconds']-.09) < .00001
    assert metrics['av_sync_residual_seconds'] < .002
    for domain, extra in (('check', []), ('golden', ['--mode', 'capture']), ('golden', ['--mode', 'verify'])):
        cli('quality', domain, '--project', fractional, '--input', mp4, '--sequence-id', sequence_id,
            '--require-audio', *extra)
    unknown = cli('quality', 'check', '--project', fractional, '--input', mp4, '--require-audio', expected=2)
    assert any(row['code'] == 'OUTPUT_AV_SYNC_OUT_OF_RANGE' for row in unknown['errors'])
    negatives.append({'name': 'unknown-author-duration', 'path': mp4.name, 'new_native_media': False,
                      'exit_code': 2, 'expected_quantization_delta_seconds': 0,
                      'errors': unknown['errors']})

    archive = public/'DP09-project.zip'
    cli('convert', 'export', '--project', fractional, '--target-format', 'package', '--output', archive)
    restored = work/'fractional-restored'
    cli('convert', 'import', '--input', archive, '--output', restored)
    rebuilt, result = render(restored, 'DP10-package-rebuild', mp4=True)
    rebuilt_rgba, rebuilt_pcm = record('DP10', rebuilt, result, width=width, height=height)
    assert np.array_equal(rebuilt_rgba, mp4_rgba) and np.array_equal(rebuilt_pcm, mp4_pcm)
    cases[-1]['decoded_rgb_aac_pcm_equal_to_development'] = True
    cases[-1]['audio_content_accepted'] = False
    save(public/'DP10-verification.json', cases[-1])

    for name, audio_duration, audio_offset, common_offset in (
            ('delayed', 4.01, .12, 0), ('advanced', 4.01, -.12, 0),
            ('short', 3.8, 0, 0), ('long', 4.3, 0, 0), ('both-shifted', 4.01, 0, .12)):
        output = public/('negative-'+name+'.mp4')
        native('-f', 'lavfi', '-i', f'color=c=0x8090a0:s={width}x{height}:r=10:d=4.1',
               '-f', 'lavfi', '-i', f'sine=frequency=371:sample_rate={SR}:duration={audio_duration}',
               '-filter_complex', f'[1:a]asetpts=PTS+{audio_offset}/TB[a]', '-map', '0:v', '-map', '[a]',
               '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', 0, '-pix_fmt', 'yuv444p',
               '-c:a', 'aac', '-output_ts_offset', common_offset, output)
        result = cli('quality', 'check', '--project', fractional, '--input', output,
                      '--sequence-id', sequence_id, '--require-audio', expected=2)
        errors = result['errors']
        assert any(row['code'] == 'OUTPUT_AV_SYNC_OUT_OF_RANGE' for row in errors), result
        picture = rgba(output, width, height)
        assert len(picture) == 41
        row = {'name': name, 'path': output.name, 'output_sha256': sha(output),
               'new_native_media': True, 'frames': len(picture), 'exit_code': 2,
               'audio_duration_authored_seconds': audio_duration, 'audio_offset_seconds': audio_offset,
               'common_offset_seconds': common_offset, 'errors': errors,
               'quality_metrics': result['data']['metrics']}
        negatives.append(row)
        if name in ('delayed', 'both-shifted'):
            old = cli('quality', 'check', '--project', fractional, '--input', output,
                      '--sequence-id', sequence_id, '--require-audio', baseline=True)
            assert old['ok']
            baseline_cases.append({'name': 'wrongly-accepted-'+name, 'base_commit': BASE,
                                   'path': output.name, 'same_input_sha256': sha(output),
                                   'old_exit_code': 0, 'new_exit_code': 2})

    font_path = previous/'DejaVuSans.ttf'
    font = ImageFont.truetype(str(font_path), 15)
    small = ImageFont.truetype(str(font_path), 13)
    y, x = np.indices((H, W))
    checker = np.where(((x//16+y//16) % 2)[:, :, None] == 0, 48, 208)

    def on_checker(frame):
        alpha = frame[:, :, 3:4].astype(float)/255
        return np.rint(frame[:, :, :3]*alpha+checker*(1-alpha)).astype(np.uint8)

    frames = []
    old_error = int(np.abs(old_picture[:, :, :, 3].astype(np.int16)-held_rgba[:, :, :, 3]).max())
    for index in range(16):
        canvas = Image.new('RGB', (W*3, H*2+72), '#101820')
        draw = ImageDraw.Draw(canvas)
        for column, (label, picture) in enumerate((('SOURCE / AUTHOR HOLD', held_rgba),
                                                  ('V51 / ALPHA FAILED', old_picture),
                                                  ('V52 / LOSSLESS ALPHA', actual))):
            draw.text((column*W+8, 8), label, font=font, fill='white')
            alpha_rgb = np.repeat(picture[index, :, :, 3:4], 3, axis=2)
            canvas.paste(Image.fromarray(alpha_rgb), (column*W, 34))
            canvas.paste(Image.fromarray(on_checker(picture[index])), (column*W, 34+H))
        draw.text((8, 38+2*H), f'frame {index:02} / {index/FPS:.2f}s | hold .50-.90s | max alpha error: V51={old_error} V52=0',
                  font=small, fill='#a9e6c4')
        frames.append(canvas)
    frames[0].save(public/'alpha-before-after.gif', save_all=True, append_images=frames[1:],
                   duration=100, loop=0, optimize=False)
    for index in (4, 7, 9, 15):
        frames[index].save(public/f'alpha-frame-{index:02}.png')
    contact = Image.new('RGB', (W*3, (H*2+72)*4), '#101820')
    for row, index in enumerate((4, 7, 9, 15)):
        contact.paste(frames[index], (0, row*(H*2+72)))
    contact.save(public/'alpha-contact.png')
    native('-i', mp4, '-an', '-vf',
           'fps=10,scale=480:-2:flags=neighbor,split[a][b];[a]palettegen[p];[b][p]paletteuse',
           public/'fractional-mp4.gif')
    # Browser-compatible source preview: a procedural checkerboard composite,
    # explicitly separate from the CLI media and scored delivery counts.
    source_preview = np.stack([on_checker(frame) for frame in np.concatenate((held_rgba[:5], held_rgba[9:]))])
    assert len(source_preview) == 12
    native('-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', FPS,
           '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-crf', 16, '-pix_fmt', 'yuv420p',
           public/'source-checkerboard.mp4', data=source_preview.tobytes())
    fractions = (9, 15, 25, 40)
    contact = Image.new('RGB', (width*2, height*2+44), '#101820')
    draw = ImageDraw.Draw(contact)
    for row, index in enumerate(fractions):
        px, py = row % 2*width, row//2*(height+22)
        draw.text((px+4, py+2), f'frame {index} / {index/FPS:.2f}s', font=small, fill='white')
        contact.paste(Image.fromarray(mp4_rgba[index, :, :, :3]), (px, py+22))
    contact.save(public/'fractional-contact.png')
    gifs = []
    for name in ('alpha-before-after.gif', 'fractional-mp4.gif'):
        with Image.open(public/name) as image:
            total = 0
            for index in range(image.n_frames):
                image.seek(index)
                total += image.info.get('duration', 0)
            gifs.append({'name': name, 'image_frames': image.n_frames, 'duration_ms': total,
                         'sha256': sha(public/name)})

    save(public/'SOURCE_RIGHTS.json', {
        'procedural_sources_and_outputs': 'CC0-1.0; generated grayscale/colour/alpha patterns, PCM and sine controls by this script',
        'inputs': {'source-ramp.mkv': sha(public/'source-ramp.mkv'), 'source-audio.wav': sha(public/'source-audio.wav')},
        'source_preview': 'checkerboard projection of the original 12 frames; not a product renderer output',
        'fractional_project_origin': str((previous/'NF06-project.zip').relative_to(ROOT)),
        'fractional_project_origin_sha256': sha(previous/'NF06-project.zip'),
        'font': {'source': str(font_path.relative_to(ROOT)), 'sha256': sha(font_path),
                 'license': str((previous/'LICENSE_DEJAVU').relative_to(ROOT)), 'not_CC0_font': True},
        'code_license_does_not_relicense_font': True})
    after = frozen()
    assert before == after
    assert len(cases) == 11 and sum(row['frames'] for row in cases) == 251
    assert sum(row.get('frames', 0) for row in negatives if row['new_native_media']) == 205
    value = {'status': 'passed_scoped_delivery_precision', 'finished_at_utc': datetime.now(timezone.utc).isoformat(),
        'cases': cases, 'negative_controls': negatives, 'baseline_cases': baseline_cases,
        'calls': calls, 'development_cli_calls': sum(not row['baseline'] for row in calls),
        'baseline_cli_calls': sum(row['baseline'] for row in calls), 'total_cli_calls': len(calls),
        'main_frames': sum(row['frames'] for row in cases),
        'main_stereo_sample_frames': sum(row['stereo_sample_frames'] for row in cases),
        'independent_original_pcm_content_frames': 76800,
        'fixed_V51_pcm_compatibility_sample_frames': 192480,
        'new_negative_control_frames': 205, 'baseline_alpha_frames': len(old_picture),
        'source_checkerboard_preview_frames': 12, 'gifs': gifs,
        'lossless_vp9_original_alpha_max_error': 0, 'lossy_alpha_exact_accepted': False,
        'frozen_before': before, 'frozen_after': after, 'frozen_equal': True,
        'new_model_forwards': 0, 'browser_invocations': 0, 'virtualization': False,
        'continuous_playback': False, 'listening_review': False, 'static_review_pending': True,
        'other_machine_accepted': False, 'all_capcut_features_and_quality_accepted': False,
        'generator_sha256': sha(Path(__file__))}
    save(public/'verification.json', value)
    save(evidence/'verification.json', value)
    print(json.dumps({key: value[key] for key in ('status', 'development_cli_calls', 'baseline_cli_calls',
                                                 'main_frames', 'main_stereo_sample_frames', 'new_negative_control_frames')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('public', 'work', 'evidence'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    run(*(getattr(args, key).resolve() for key in ('public', 'work', 'evidence')))
