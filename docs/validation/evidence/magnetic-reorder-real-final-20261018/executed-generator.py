"""Native CLI permutations with original frame/PCM truth and explicit graph references."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
TPS, FPS, W, H, SR = 90000, 10, 160, 64, 48000
BASE = 'bcab0e052e4e11d10696b8761c26fdd6f87666cf'


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
    calls, cases, negatives = [], [], []
    env = dict(os.environ)
    env.update(TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'),
               TMPDIR=str(ROOT/'product/.runtime/temp'), PYTHONDONTWRITEBYTECODE='1')
    bootstrap = ('import sys;sys.path.insert(0,sys.argv.pop(1));'
                 'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
                 'from ai_ad_editor.cli import main;raise SystemExit(main())')

    def cli(*args, expected=0):
        command = [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap,
                   str(ROOT/'product/src'), *map(str, args)]
        start = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=360)
        index = len(calls)+1
        (evidence/f'{index:03}.stdout.json').write_bytes(result.stdout)
        (evidence/f'{index:03}.stderr.log').write_bytes(result.stderr)
        calls.append({'index': index, 'args': list(map(str, args)), 'exit_code': result.returncode,
            'expected_exit_code': expected, 'seconds': time.monotonic()-start,
            'stdout_sha256': digest(result.stdout), 'stderr_sha256': digest(result.stderr)})
        save(evidence/'calls.json', calls)
        value = json.loads(result.stdout.decode('utf-8-sig')) if result.stdout else {'stderr': result.stderr.decode('utf-8', 'replace')}
        print(json.dumps({'cli_call': index, 'command': list(map(str, args[:2])), 'exit_code': result.returncode}), flush=True)
        assert result.returncode == expected, (calls[-1], value)
        return value

    def native(*args, data=None):
        done = subprocess.run(['ffmpeg', '-v', 'error', '-y', *map(str, args)], input=data,
                              capture_output=True, timeout=180)
        assert done.returncode == 0, done.stderr.decode('utf-8', 'replace')
        return done.stdout

    def picture(path, *, alpha=False, width=W, height=H):
        options = ['-c:v', 'libvpx-vp9'] if alpha and path.suffix == '.webm' else []
        raw = native(*options, '-i', path, '-map', '0:v:0', '-an', '-fps_mode', 'passthrough',
                     '-pix_fmt', 'rgba' if alpha else 'rgb24', '-f', 'rawvideo', 'pipe:1')
        return np.frombuffer(raw, dtype=np.uint8).reshape(-1, height, width, 4 if alpha else 3)

    def pcm(path):
        raw = native('-i', path, '-map', '0:a:0', '-vn', '-ar', SR, '-ac', 2, '-f', 'f32le', 'pipe:1')
        return np.frombuffer(raw, dtype='<f4').reshape(-1, 2)

    def ingest(project, path, aid, *, font=False):
        return cli('media', 'ingest', '--project', project, '--input', path, '--asset-id', aid,
            '--verification-status', 'verified', '--permitted-use', 'commercial_ad',
            '--license-spdx', 'Bitstream-Vera' if font else 'CC0-1.0',
            '--source', 'existing unmodified DejaVu Sans' if font else 'self-authored procedural frames and PCM',
            '--creator', 'DejaVu and Bitstream font authors' if font else 'project procedural fixture authors',
            '--evidence', public/('LICENSE_DEJAVU' if font else 'SOURCE_RIGHTS.json'))

    def clip(cid, start, aid='frames', **fields):
        return {'id': cid, 'asset_id': aid, 'timeline_start_tick': start, 'duration_tick': TPS,
            'source_in_tick': (ord(cid[-1])-ord('a')+1)*TPS,
            'source_out_tick': (ord(cid[-1])-ord('a')+2)*TPS, **fields}

    def track(tid, kind, clips, order=0, **fields):
        return {'id': tid, 'kind': kind, 'order': order, 'clips': clips, **fields}

    def author(project, payload):
        save(project/'project.json', payload)

    def request(ids=('c',), target='a', **fields):
        return {'action': 'reorder', 'clip_ids': list(ids), 'before_clip_id': target, **fields}

    def apply(project, query, *, transaction=False):
        path = work/(project.name+'-request.json');save(path, query)
        raw = (project/'project.json').read_bytes()
        preview = cli('timeline', 'edit', '--project', project, '--input', path, '--dry-run')
        assert raw == (project/'project.json').read_bytes()
        base = preview['data']['plan']['base_project_sha256']
        args = ['timeline', 'edit', '--project', project, '--input', path, '--expected-project-sha256', base]
        if transaction: args += ['--idempotency-key', 'native-reorder']
        value = cli(*args)
        if transaction:
            edited = (project/'project.json').read_bytes()
            replay = cli(*args)
            assert value['operation_id'] == replay['operation_id'] and edited == (project/'project.json').read_bytes()
            stale = cli('timeline', 'edit', '--project', project, '--input', path,
                        '--expected-project-sha256', base, expected=2)
            assert stale['errors'][0]['code'] == 'EDIT_PROJECT_CHANGED' and edited == (project/'project.json').read_bytes()
            negatives.append({'name': 'stale_plan', 'code': stale['errors'][0]['code'], 'author_unchanged': True})
        cli('validate', '--project', project, '--strict-rights')
        cli('policy', 'audit', '--project', project)
        return value

    def render(project, name, *, alpha=False, sequence_id=None):
        output = project/'renders'/(name+('.webm' if alpha else '.mkv'))
        args = ['render', '--project', project, '--output', output, '--crf', '0', '--publish']
        args += (['--container', 'webm', '--video-codec', 'libvpx-vp9', '--audio-codec', 'libopus',
                  '--pixel-format', 'yuva420p'] if alpha else
                 ['--container', 'mkv', '--audio-codec', 'pcm_f32le', '--pixel-format', 'yuv444p'])
        if sequence_id: args += ['--sequence-id', sequence_id]
        result = cli(*args)
        shutil.copyfile(output, public/output.name)
        shutil.copyfile(Path(result['data']['manifest']), evidence/(name+'.manifest.json'))
        return output, result

    def record(project, name, expected, expected_audio, *, scope='independent-original-frame-permutation-and-PCM',
               alpha=False, width=W, height=H):
        output, result = render(project, name, alpha=alpha)
        actual, audio = picture(output, alpha=alpha, width=width, height=height), pcm(output)
        assert actual.shape == expected.shape, (name, actual.shape, expected.shape)
        delta = np.abs(actual.astype(np.int16)-expected.astype(np.int16))
        error = int(delta[:, :, :, 3].max()) if alpha else int(delta.max())
        assert error == 0, (name, error)
        assert np.isfinite(audio).all()
        audio_error = None
        if expected_audio is not None:
            assert audio.shape == expected_audio.shape, (name, audio.shape, expected_audio.shape)
            audio_error = float(np.max(np.abs(audio-expected_audio)))
            assert audio_error <= 2e-6, (name, audio_error)
        probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(output)]))
        pts = [float(v['best_effort_timestamp_time']) for v in probe['frames']]
        assert len(pts) == len(actual)
        pts_error = max(abs(t-i/FPS) for i, t in enumerate(pts));assert pts_error <= .00051
        p = json.loads((project/'project.json').read_bytes())
        assert not any(a['id'].startswith('__') for a in p['assets'])
        row = {'name': name, 'scope': scope, 'path': output.name, 'frames': len(actual),
            'width': width, 'height': height, 'stereo_sample_frames': len(audio),
            'threshold_exact_rgb_or_alpha': 0, 'max_alpha_error' if alpha else 'max_rgb_error': error,
            'audio_content_accepted': expected_audio is not None, 'max_pcm_error': audio_error,
            'threshold_pcm_error': 2e-6, 'all_pts_checked': True, 'max_pts_error_seconds': pts_error,
            'output_sha256': sha(output), 'decoded_picture_sha256': digest(actual.tobytes()),
            'decoded_pcm_sha256': digest(audio.tobytes()), 'quality': result['data']['quality'],
            'delivery': result['data']['delivery'], 'new_model_forwards': 0}
        save(public/(name+'-verification.json'), row);cases.append(row)
        if not alpha:
            native('-i', output, '-c:v', 'libx264', '-crf', 16, '-pix_fmt', 'yuv420p', '-c:a', 'aac', public/(name+'.mp4'))
        return actual, audio

    def package(project, name):
        cli('convert', 'export', '--project', project, '--target-format', 'package', '--output', public/(name+'-project.zip'))

    try:
        font_source = ROOT/'docs/assets/boundary-readable-font-20261018'
        shutil.copyfile(font_source/'DejaVuSans.ttf', public/'DejaVuSans.ttf')
        shutil.copyfile(font_source/'LICENSE_DEJAVU', public/'LICENSE_DEJAVU')
        font = ImageFont.truetype(str(public/'DejaVuSans.ttf'), 19)
        source = np.zeros((60, H, W, 3), dtype=np.uint8)
        for i in range(60):
            # Mode 1 deliberately excludes color-space round-trip rounding.
            image = Image.new('1', (W, H));draw = ImageDraw.Draw(image)
            draw.text((4, 1), f'SOURCE {i:02}', font=font, fill=1)
            draw.rectangle((3+(i*3) % 130, 30, 23+(i*3) % 130, 47), fill=1)
            for bit in range(6):
                if i & (1 << bit): draw.rectangle((4+bit*25, 52, 23+bit*25, 60), fill=1)
            source[i] = np.array(image.convert('RGB'))
        original = public/'source-frames.mkv'
        native('-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', FPS, '-i', 'pipe:0',
               '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgra', original, data=source.tobytes())
        assert np.array_equal(picture(original), source)
        n = np.arange(6*SR)/SR
        signal = np.stack((.05*np.sin(2*np.pi*(120*n+3*n*n))+.015*n,
                           .04*np.cos(2*np.pi*(210*n+2*n*n))-.01*n), axis=1).astype('<f4')
        sound = public/'source-audio.wav'
        native('-f', 'f32le', '-ar', SR, '-ac', 2, '-i', 'pipe:0', '-c:a', 'pcm_f32le', sound, data=signal.tobytes())
        save(public/'SOURCE_RIGHTS.json', {'source-frames.mkv': sha(original), 'source-audio.wav': sha(sound),
            'procedural_sources_and_outputs': 'CC0-1.0; self-authored binary counters, moving boxes, alpha and PCM',
            'font': 'unmodified DejaVu Sans; original license in LICENSE_DEJAVU, not CC0',
            'font_sha256': sha(public/'DejaVuSans.ttf'), 'generator_sha256': sha(Path(__file__)),
            'models': 0, 'browser_invocations': 0, 'virtualization': False})
        native('-i', original, '-i', sound, '-c:v', 'libx264', '-crf', 16, '-pix_fmt', 'yuv420p',
               '-c:a', 'aac', public/'source-preview.mp4')
        base = work/'base';cli('project', 'init', base)
        ingest(base, original, 'frames');ingest(base, sound, 'sound');ingest(base, public/'DejaVuSans.ttf', 'font', font=True)
        author_base = json.loads((base/'project.json').read_bytes())
        root_id = author_base['sequences'][0]['id']
        author_base['settings']['canvas'].update(width=W, height=H)
        author_base['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
        author_base['sequences'] = [{'id': root_id, 'name': 'original four shots', 'duration_tick': 4*TPS,
            'tracks': [track('main', 'video', [clip(c, i*TPS, link_id=c+'g') for i, c in enumerate('abcd')]),
                       track('voice', 'audio', [clip('v'+c, i*TPS, 'sound', link_id=c+'g') for i, c in enumerate('abcd')], 1)]}]
        author(base, author_base)

        def make(name):
            project = work/name;shutil.copytree(base, project);return project, copy.deepcopy(author_base)

        def truth(order):
            return (np.concatenate([source[(ord(c)-96)*10:(ord(c)-95)*10] for c in order]),
                    np.concatenate([signal[(ord(c)-96)*SR:(ord(c)-95)*SR] for c in order]))

        project, p = make('MR01');package(project, 'MR01-before')
        apply(project, request(), transaction=True)
        first, _ = record(project, 'MR01', *truth('cabd'));package(project, 'MR01')
        project, p = make('MR02');apply(project, request(('d', 'b')))
        record(project, 'MR02', *truth('bdac'))
        apply(project, request(('b', 'd'), None));record(project, 'MR02-end', *truth('acbd'))

        project, p = make('MR03')
        for t in p['sequences'][0]['tracks']:
            for c, at in zip(t['clips'], (.2, 1.5, 3, 4)): c['timeline_start_tick'] = round(at*TPS)
        bed = clip('d', 0, 'sound', id='music_bed', duration_tick=4*TPS, source_in_tick=0, source_out_tick=4*TPS)
        p['sequences'][0]['tracks'].append(track('bed', 'audio', [bed], 2, audio={'volume': .1}, sync_lock=False))
        p['sequences'][0]['duration_tick'] = 5*TPS;author(project, p)
        apply(project, request(options={'linkage': True}))
        expected_video, expected_audio = truth('cabd')
        record(project, 'MR03', expected_video, expected_audio+signal[:4*SR]*.1)

        # Full complex author graph, including nested freeze/captions, reversed
        # stepped retiming, a retained presentation window and own animation.
        project = work/'MR04'
        old_package = ROOT/'docs/assets/nested-freeze-v51-final-20261018/NF06-project.zip'
        cli('convert', 'import', '--input', old_package, '--output', project)
        ingest(project, original, 'frames')
        p = json.loads((project/'project.json').read_bytes())
        old_root = p['sequences'][0];old_root['id'] = 'complex_child'
        complex_clip = {'id': 'complex', 'sequence_id': 'complex_child', 'timeline_start_tick': TPS,
            'duration_tick': 2*TPS, 'source_in_tick': 0, 'source_out_tick': 4*TPS, 'reverse': True,
            'speed_curve': {'keyframes': [{'at_tick': 0, 'speed': 1, 'interpolation': 'hold'},
                                         {'at_tick': 2*TPS, 'speed': 2, 'interpolation': 'hold'}]},
            'presentation_window': {'version': 1, 'authored_start_tick': TPS, 'authored_duration_tick': 3*TPS, 'offset_tick': TPS},
            'keyframes': [{'property': 'transform.opacity', 'keyframes': [
                {'at_tick': 0, 'value': .6, 'interpolation': 'linear'},
                {'at_tick': 3*TPS, 'value': 1, 'interpolation': 'linear'}]}]}
        p['sequences'].insert(0, {'id': 'reorder_root', 'name': 'complex reorder', 'duration_tick': 3*TPS,
            'tracks': [track('reorder_main', 'video', [clip('a', 0), complex_clip])]})
        author(project, p)
        width, height = p['settings']['canvas']['width'], p['settings']['canvas']['height']
        reference_path, _ = render(project, 'MR04-before')
        old_video, old_audio = picture(reference_path, width=width, height=height), pcm(reference_path)
        apply(project, request(('complex',)))
        record(project, 'MR04', np.concatenate((old_video[10:30], old_video[:10])),
               np.concatenate((old_audio[SR:3*SR], old_audio[:SR])), width=width, height=height,
               scope='same-renderer-full-author-block-reference; not independent glyph or retiming math')
        package(project, 'MR04')

        project, p = make('MR05')
        p['sequences'][0]['source_transitions'] = [{'id': 'bc', 'type': 'dissolve', 'duration_tick': TPS//5,
            'from_clip_id': 'b', 'to_clip_id': 'c', 'audio_pairs': [{'from_clip_id': 'vb', 'to_clip_id': 'vc'}]}]
        author(project, p)
        reference_path, _ = render(project, 'MR05-before')
        old_video, old_audio = picture(reference_path), pcm(reference_path)
        apply(project, request(('b', 'c')))
        record(project, 'MR05', np.concatenate((old_video[10:30], old_video[:10], old_video[30:])),
               np.concatenate((old_audio[SR:3*SR], old_audio[:SR], old_audio[3*SR:])),
               scope='same-renderer-whole-neighbor-block; transition blend not an independent new oracle')
        package(project, 'MR05')

        project, p = make('MR06')
        p['sequences'][0]['source_transitions'] = [{'id': 'ab', 'type': 'dissolve', 'duration_tick': TPS//5,
            'from_clip_id': 'a', 'to_clip_id': 'b', 'audio_pairs': []}]
        author(project, p)
        req = work/'MR06-conflict.json';save(req, request(('b',), 'd'))
        unchanged = (project/'project.json').read_bytes()
        result = cli('timeline', 'edit', '--project', project, '--input', req, expected=2)
        assert result['errors'][0]['code'] == 'EDIT_REORDER_TRANSITION_CONFLICT'
        assert unchanged == (project/'project.json').read_bytes()
        negatives.append({'name': 'broken_transition', 'code': result['errors'][0]['code'], 'author_unchanged': True})
        apply(project, request(('b',), 'd', transition_policy='drop_broken'))
        record(project, 'MR06', *truth('acbd'))

        project, p = make('MR07')
        caption = {'id': 'caption', 'generator': {'type': 'text'}, 'timeline_start_tick': 2*TPS,
            'duration_tick': TPS, 'source_in_tick': 0, 'source_out_tick': TPS,
            'subtitle': {'text': 'C RIDER', 'style': {'font_asset_id': 'font', 'fontsize': 12,
                'x': '4', 'y': '35', 'fontcolor': 'white', 'box': False}}}
        p['sequences'][0]['tracks'].append(track('captions', 'subtitle', [caption], 2))
        p['sequences'][0]['tracks'].append(track('bed', 'audio', [bed], 3, audio={'volume': .1}, sync_lock=False))
        author(project, p)
        reference_path, _ = render(project, 'MR07-before');old_video = picture(reference_path)
        apply(project, request(options={'sync': True, 'linkage': True}))
        expected_video, expected_audio = truth('cabd')
        record(project, 'MR07', np.concatenate((old_video[20:30], old_video[:20], old_video[30:])),
               expected_audio+signal[:4*SR]*.1,
               scope='same-renderer-subtitle-glyph-reference; independent-original-PCM-plus-opt-out-bed')
        package(project, 'MR07')

        y, x = np.indices((H, W));alpha = np.empty((60, H, W, 4), dtype=np.uint8)
        alpha[:, :, :, :3] = source
        for i in range(60): alpha[i, :, :, 3] = (x+7*y+19*i) % 256
        alpha_source = public/'source-alpha.webm'
        native('-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{W}x{H}', '-r', FPS, '-i', 'pipe:0', '-an',
               '-c:v', 'libvpx-vp9', '-b:v', 0, '-lossless', 1, '-pix_fmt', 'yuva420p', alpha_source, data=alpha.tobytes())
        assert np.array_equal(picture(alpha_source, alpha=True)[:, :, :, 3], alpha[:, :, :, 3])
        project, p = make('MR08');ingest(project, alpha_source, 'alpha')
        p = json.loads((project/'project.json').read_bytes())
        for c in p['sequences'][0]['tracks'][0]['clips']: c['asset_id'] = 'alpha'
        author(project, p);apply(project, request())
        expected_alpha = np.concatenate([alpha[(ord(c)-96)*10:(ord(c)-95)*10] for c in 'cabd'])
        record(project, 'MR08', expected_alpha, None, alpha=True,
               scope='independent-original-256-level-alpha; RGB420-and-Opus-content-not-lossless-claims')
        package(project, 'MR08')

        # These are actual CLI rejection/rollback executions, not media renders.
        for name, setup, query, code in (
            ('locked_link', lambda p: (p['sequences'][0]['tracks'][1].update(locked=True)), request(), 'EDIT_TRACK_LOCKED'),
            ('sync_span', lambda p: p['sequences'][0]['tracks'].append(track('bed', 'audio', [bed], 2)), request(options={'sync': True}), 'EDIT_REORDER_SYNC_SPAN_UNSUPPORTED'),
            ('negative_link', lambda p: p['sequences'][0]['tracks'][1]['clips'][2].update(timeline_start_tick=TPS), request(), 'EDIT_NEGATIVE_TIME'),
        ):
            project, p = make('negative-'+name);setup(p);author(project, p)
            req = work/(name+'.json');save(req, query);unchanged = (project/'project.json').read_bytes()
            result = cli('timeline', 'edit', '--project', project, '--input', req, expected=2)
            assert result['errors'][0]['code'] == code, result
            assert unchanged == (project/'project.json').read_bytes()
            negatives.append({'name': name, 'code': code, 'author_unchanged': True, 'new_media': False})

        # Reimport and render the same complex author graph without flattening.
        restored = work/'restored';cli('convert', 'import', '--input', public/'MR04-project.zip', '--output', restored)
        assert json.loads((restored/'project.json').read_bytes())['sequences'] == json.loads((work/'MR04/project.json').read_bytes())['sequences']
        reference = next(row for row in cases if row['name'] == 'MR04')
        expected_video = picture(public/'MR04.mkv', width=reference['width'], height=reference['height'])
        record(restored, 'MR09-package', expected_video, pcm(public/'MR04.mkv'), width=reference['width'], height=reference['height'],
               scope='package-development-reference-not-an-additional-independent-clock-oracle')

        # Before/after visual comparison, always sourced from the actual CLI output.
        original_four, _ = truth('abcd')
        tiles = []
        for index in range(40):
            image = Image.new('RGB', (W*4, H*2+48), '#102030');draw = ImageDraw.Draw(image)
            draw.text((8, 3), 'BEFORE A B C D       AFTER C A B D', font=font, fill='white')
            image.paste(Image.fromarray(original_four[index]).resize((W*2, H*2), Image.Resampling.NEAREST), (0, 30))
            image.paste(Image.fromarray(first[index]).resize((W*2, H*2), Image.Resampling.NEAREST), (W*2, 30))
            draw.text((8, H*2+29), f't={index/FPS:.1f}s / exact frames + linked PCM', fill='white')
            tiles.append(image)
        tiles[0].save(public/'reorder-before-after.gif', save_all=True, append_images=tiles[1:], duration=100, loop=0, optimize=False)
        contact = Image.new('RGB', (W*4, (H*2+48)*4), '#102030')
        for row, index in enumerate((5, 15, 25, 35)):
            tiles[index].save(public/f'reorder-frame-{index:02}.png');contact.paste(tiles[index], (0, row*(H*2+48)))
        contact.save(public/'reorder-contact.png')
        after = frozen();assert before == after
        value = {'status': 'passed_scoped_magnetic_reorder', 'base_commit': BASE,
            'finished_at_utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
            'calls': calls, 'development_cli_calls': len(calls), 'negative_controls': negatives,
            'main_frames': sum(row['frames'] for row in cases),
            'main_stereo_sample_frames': sum(row['stereo_sample_frames'] for row in cases),
            'independent_PCM_case_names': ['MR01', 'MR02', 'MR02-end', 'MR03', 'MR06', 'MR07'],
            'complex_and_caption_reference_limit': 'same-renderer decoded pre-edit complete blocks; no independent glyph/curve-quality claim',
            'source_scope': 'binary grayscale pure-cut RGB exact; not a general color-conversion-fidelity claim',
            'reference_before_renders': ['MR04-before', 'MR05-before', 'MR07-before'],
            'frozen_before': before, 'frozen_after': after, 'frozen_equal': True,
            'generator_sha256': sha(Path(__file__)), 'new_model_forwards': 0, 'browser_invocations': 0,
            'virtualization': False, 'continuous_playback': False, 'listening_review': False,
            'static_review_pending': True, 'other_machine_accepted': False, 'all_capcut_features_and_quality_accepted': False}
        value['files'] = {path.name: {'sha256': sha(path), 'bytes': path.stat().st_size}
                          for path in sorted(public.iterdir()) if path.is_file()}
        save(public/'verification.json', value);save(evidence/'verification.json', value)
        print(json.dumps({k: value[k] for k in ('status', 'development_cli_calls', 'main_frames', 'main_stereo_sample_frames')}))
    except BaseException as exc:
        save(evidence/'failure.json', {'error': repr(exc), 'calls': calls, 'frozen_before': before,
                                     'frozen_after': frozen(), 'partials_preserved': True})
        save(public/'STATUS.json', {'status': 'failed_partial_run', 'error': repr(exc), 'not_a_complete_release': True})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('public', 'work', 'evidence'): parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    run(*(getattr(args, key).resolve() for key in ('public', 'work', 'evidence')))
