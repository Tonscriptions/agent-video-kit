"""Eight native range edits against complete authors rendered by fixed V38.

References select/concatenate decoded original RGB and float PCM, without
calling the new planner. The old renderer is the same product, not an
independent image/retiming oracle. All inputs are original CC0 fixtures.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from smoke_fragments import frozen, save, sha

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '2aa52297511b701bd7d05135afb5c9c726bb55ac'
TPS, FPS, W, H, SR = 90000, 10, 240, 136, 48000


def run(public, work):
    import numpy as np
    from PIL import Image

    public.mkdir(parents=True, exist_ok=False)
    work.mkdir(parents=True, exist_ok=False)
    before, calls, results = frozen(), [], []
    baseline = work / 'fixed-v38'
    save(public / 'run-state.json', {'status': 'running', 'source_before': before})
    archive = subprocess.check_output(['git', '-c', 'core.autocrlf=false', 'archive', '--format=zip',
        BASELINE, 'product/src', 'docs/specs/agent-project.schema.json'], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for item in z.infolist():
            if item.is_dir():
                continue
            target = (baseline / item.filename).resolve()
            assert target.is_relative_to(baseline.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(item))
    old_hashes = {p.relative_to(baseline).as_posix(): sha(p) for p in baseline.rglob('*') if p.is_file()}
    boot = ('import sys;sys.path.insert(0,sys.argv.pop(1));'
        'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
        'from ai_ad_editor.cli import main;raise SystemExit(main())')

    def cli(*args, old=False, expected=0, code=None):
        started = time.monotonic()
        process = subprocess.run([sys.executable, '-E', '-B', '-X', 'utf8', '-c', boot,
            str(baseline / 'product/src' if old else ROOT / 'product/src'), *map(str, args)],
            cwd=ROOT, capture_output=True, timeout=300)
        index = len(calls)
        for label, raw in [('stdout', process.stdout), ('stderr', process.stderr)]:
            (public / f'cli-{index:03}-{label}.log').write_bytes(raw)
        value = json.loads(process.stdout.decode('utf-8-sig'))
        row = {'index': index, 'args': list(map(str, args)), 'fixed_v38': old,
            'exit_code': process.returncode, 'expected_exit_code': expected,
            'seconds': time.monotonic() - started,
            'stdout_sha256': 'sha256:' + hashlib.sha256(process.stdout).hexdigest(),
            'stderr_sha256': 'sha256:' + hashlib.sha256(process.stderr).hexdigest()}
        if code:
            row['expected_error_code'] = code
        calls.append(row)
        save(public / 'calls-in-progress.json', calls)
        assert process.returncode == expected, value
        if code:
            assert value['errors'][0]['code'] == code, value
        return value

    def ff(args):
        process = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', *map(str, args)],
            capture_output=True, timeout=180)
        assert process.returncode == 0, process.stderr.decode('utf-8', 'replace')

    def decode(path):
        video = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
            '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'])
        audio = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
            '-vn', '-ar', str(SR), '-ac', '2', '-f', 'f32le', 'pipe:1'])
        return (np.frombuffer(video, dtype=np.uint8).reshape(-1, H, W, 3),
            np.frombuffer(audio, dtype='<f4').reshape(-1, 2))

    def join(*parts):
        return tuple(np.concatenate([p[i] for p in parts]) for i in (0, 1))

    def select(media, first, last=None):
        return media[0][int(first*FPS):None if last is None else int(last*FPS)], \
            media[1][int(first*SR):None if last is None else int(last*SR)]

    def take(clip, first, last, at):
        result = copy.deepcopy(clip)
        result['presentation_window'] = {'version': 1, 'authored_start_tick': clip['timeline_start_tick'],
            'authored_duration_tick': clip['duration_tick'], 'offset_tick': int(first*TPS)}
        result.update(timeline_start_tick=int(at*TPS), duration_tick=int((last-first)*TPS))
        return result

    try:
        fixture = ROOT / 'docs/assets/source-transitions-20261017'
        for name in ('source-a.mp4', 'sound-a.wav'):
            shutil.copyfile(fixture / name, public / name)
        shutil.copyfile(ROOT / 'docs/assets/fragments-20261018/agent-grid-cc0.ttf', public / 'agent-grid-cc0.ttf')
        (public / 'captions.srt').write_text('1\n00:00:02,000 --> 00:00:03,000\nCTA\n', encoding='utf-8')
        provenance = {'license_spdx': 'CC0-1.0', 'source': 'V35 original counter/audio, V37 original grid font, new CTA cue',
            'files': {p.name: sha(p) for p in public.iterdir() if p.suffix in {'.mp4', '.wav', '.ttf', '.srt'}},
            'new_model_inference': 0, 'network_runtime': False, 'virtualization': False}
        save(public / 'fixture-provenance.json', provenance)
        seed = work / 'seed'
        cli('project', 'init', seed)
        rights = ['--verification-status', 'verified', '--license-spdx', 'CC0-1.0',
            '--permitted-use', 'commercial_ad', '--evidence', public / 'fixture-provenance.json']
        for aid, name in [('video', 'source-a.mp4'), ('audio', 'sound-a.wav'),
                ('font', 'agent-grid-cc0.ttf'), ('captions', 'captions.srt')]:
            cli('media', 'ingest', '--project', seed, '--input', public / name, '--asset-id', aid, *rights)
        original = json.loads((seed / 'project.json').read_text(encoding='utf-8'))
        original['settings']['canvas'] = {'width': W, 'height': H}
        original['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
        original['sequences'][0]['duration_tick'] = 4*TPS

        def author(prefix, source=1, duration=4, reverse=False, motion=False):
            project = copy.deepcopy(original)
            sequence = project['sequences'][0]
            sequence['duration_tick'] = int(duration*TPS)
            for track, asset, suffix in zip(sequence['tracks'], ['video', 'audio'], ['v', 'a']):
                clip = {'id': prefix+suffix, 'asset_id': asset, 'timeline_start_tick': 0,
                    'duration_tick': int(duration*TPS), 'source_in_tick': int(source*TPS),
                    'source_out_tick': int((source+duration)*TPS), 'link_id': prefix, 'reverse': reverse}
                if motion and suffix == 'v':
                    clip['keyframes'] = [{'property': 'transform.position.x', 'keyframes': [
                        {'at_tick': 0, 'value': .5, 'interpolation': 'ease_in_out'},
                        {'at_tick': int(duration*TPS), 'value': .65, 'interpolation': 'linear'}]}]
                if motion and suffix == 'a':
                    clip['audio'] = {'fade_in': .3, 'fade_out': .4}
                track['clips'] = [clip]
            return project

        def project_at(name, project):
            path = work / name
            shutil.copytree(seed, path)
            save(path / 'project.json', project)
            save(public / f'{name}-project.json', project)
            return path

        def render(path, name, old=False):
            movie = path / 'renders' / f'{name}.mkv'
            response = cli('render', '--project', path, '--output', movie, '--container', 'mkv',
                '--crf', 0, '--pixel-format', 'yuv444p', '--audio-codec', 'pcm_f32le', '--publish', old=old)
            shutil.copyfile(movie, public / f'{name}.mkv')
            ff(['-i', movie, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', public / f'{name}.mp4'])
            save(public / f'{name}-render.json', response)
            return decode(movie)

        new_project = author('N', 6, 1)
        new_media = render(project_at('incoming', new_project), 'incoming', old=True)
        items = [{'track_id': t['id'], 'clip': t['clips'][0]} for t in new_project['sequences'][0]['tracks']]
        base = author('B')
        originals, expectations, actuals, paths, digests = {}, {}, {}, {}, {}

        def edit_case(name, project, request, expected=None):
            path = project_at(name+'-before', project)
            prior = render(path, name+'-original', old=True)
            original_bytes = (path / 'project.json').read_bytes()
            req = work / f'{name}-request.json'
            save(req, request)
            save(public / req.name, request)
            cli('timeline', 'edit', '--project', path, '--input', req, '--dry-run', old=True,
                expected=2, code='EDIT_REQUEST_INVALID')
            assert original_bytes == (path / 'project.json').read_bytes()
            preview = cli('timeline', 'edit', '--project', path, '--input', req, '--dry-run')
            assert original_bytes == (path / 'project.json').read_bytes()
            digest = preview['data']['plan']['base_project_sha256']
            cli('timeline', 'edit', '--project', path, '--input', req,
                '--expected-project-sha256', digest, '--idempotency-key', name)
            saved = (path / 'project.json').read_bytes()
            cli('timeline', 'edit', '--project', path, '--input', req,
                '--expected-project-sha256', digest, '--idempotency-key', name)
            assert saved == (path / 'project.json').read_bytes()
            cli('validate', '--project', path, '--strict-rights')
            actual = render(path, name+'-actual')
            expected = expected(prior) if callable(expected) else expected
            assert actual[0].shape == expected[0].shape and actual[1].shape == expected[1].shape
            pixels = np.abs(actual[0].astype(np.int16)-expected[0].astype(np.int16))
            pcm = np.abs(actual[1]-expected[1])
            row = {'case': name, 'action': request['action'], 'frames': len(actual[0]),
                'stereo_sample_frames': len(actual[1]), 'max_rgb_difference': int(pixels.max()),
                'max_pcm_difference': float(pcm.max()), 'status': 'passed' if not pixels.any() and not pcm.any() else 'failed',
                'rgb_sha256': 'sha256:'+hashlib.sha256(actual[0].tobytes()).hexdigest(),
                'pcm_sha256': 'sha256:'+hashlib.sha256(actual[1].tobytes()).hexdigest(),
                'plan': preview['data']['plan']}
            save(public / f'{name}-verification.json', row)
            results.append(row)
            assert row['status'] == 'passed', row
            save(public / f'{name}-actual-project.json', json.loads(saved.decode('utf-8')))
            originals[name], expectations[name], actuals[name], paths[name], digests[name] = prior, expected, actual, path, digest
            return prior

        edit_case('R01', base, {'action': 'insert', 'at_tick': TPS, 'items': items},
            lambda m: join(select(m, 0, 1), new_media, select(m, 1)))
        complex_project = author('B', reverse=True, motion=True)
        for track in complex_project['sequences'][0]['tracks']:
            track['clips'][0]['speed_curve'] = {'keyframes': [
                {'at_tick': 0, 'speed': .5, 'interpolation': 'ease_in_out'},
                {'at_tick': 4*TPS, 'speed': 1.5, 'interpolation': 'linear'}]}
        edit_case('R02', complex_project, {'action': 'overwrite', 'at_tick': TPS, 'items': items},
            lambda m: join(select(m, 0, 1), new_media, select(m, 2)))
        disabled = copy.deepcopy(complex_project)
        disabled['sequences'][0]['tracks'][0]['clips'][0].pop('keyframes')
        no_motion = render(project_at('R02-no-motion', disabled), 'R02-no-motion', old=True)
        assert not np.array_equal(no_motion[0], originals['R02'][0])
        zeros = (np.zeros_like(new_media[0]), np.zeros_like(new_media[1]))
        for name, action in [('R03', 'lift'), ('R04', 'extract')]:
            edit_case(name, base, {'action': action, 'at_tick': TPS, 'duration_tick': TPS,
                'track_ids': [t['id'] for t in base['sequences'][0]['tracks']]},
                (lambda m: join(select(m, 0, 1), zeros, select(m, 2))) if action == 'lift'
                else (lambda m: join(select(m, 0, 1), select(m, 2))))
        left, right, middle = author('L', motion=True), author('R', 3, reverse=True, motion=True), author('M', 5, 1, motion=True)
        lm = render(project_at('left-author', left), 'left-author', old=True)
        rm = render(project_at('right-author', right), 'right-author', old=True)
        mm = render(project_at('middle-author', middle), 'middle-author', old=True)
        rolling, sliding = copy.deepcopy(left), copy.deepcopy(left)
        for target, st, lt, rt, mt in zip(rolling['sequences'][0]['tracks'], sliding['sequences'][0]['tracks'],
                left['sequences'][0]['tracks'], right['sequences'][0]['tracks'], middle['sequences'][0]['tracks']):
            target['clips'] = [take(lt['clips'][0], 0, 2, 0), take(rt['clips'][0], 2, 4, 2)]
            mid = copy.deepcopy(mt['clips'][0]); mid['timeline_start_tick'] = TPS
            st['clips'] = [take(lt['clips'][0], 0, 1, 0), mid, take(rt['clips'][0], 2, 4, 2)]
        edit_case('R05', rolling, {'action': 'roll', 'left_clip_id': 'Lv', 'right_clip_id': 'Rv', 'delta_tick': TPS},
            join(select(lm, 0, 3), select(rm, 3)))
        edit_case('R06', sliding, {'action': 'slide', 'clip_id': 'Mv', 'delta_tick': TPS//2},
            join(select(lm, 0, 1.5), mm, select(rm, 2.5)))
        nested = copy.deepcopy(base)
        child = copy.deepcopy(new_project['sequences'][0]); child['id'] = 'child'
        for t in child['tracks']:
            t['id'] = 'child_'+t['id']
        child['tracks'][1]['audio'] = {'volume': .6}
        nested['sequences'].append(child)
        child_ref = copy.deepcopy(new_project); child_ref['sequences'][0]['tracks'][1]['audio'] = {'volume': .6}
        cm = render(project_at('processed-child', child_ref), 'processed-child', old=True)
        container = {'id': 'group', 'sequence_id': 'child', 'timeline_start_tick': 0, 'duration_tick': TPS,
            'source_in_tick': 0, 'source_out_tick': TPS}
        edit_case('R07', nested, {'action': 'insert', 'at_tick': TPS,
            'items': [{'track_id': 'track_video_1', 'clip': container}], 'options': {'sync': True}},
            lambda m: join(select(m, 0, 1), cm, select(m, 1)))
        captions = copy.deepcopy(base)
        font = next(a for a in captions['assets'] if a['id'] == 'font')
        captions['sequences'][0]['tracks'].append({'id': 'subtitles', 'kind': 'subtitle', 'order': 2,
            'clips': [{'id': 'CTA', 'asset_id': 'captions', 'timeline_start_tick': 2*TPS, 'duration_tick': TPS,
                'source_in_tick': 0, 'source_out_tick': TPS,
                'subtitle': {'style': {'fontfile': font['uri'], 'font_asset_id': 'font', 'font_size': 24}}}]})
        edit_case('R08', captions, {'action': 'insert', 'at_tick': TPS, 'items': items, 'options': {'linkage': True}},
            lambda m: join(select(m, 0, 1), new_media, select(m, 1)))
        assert not np.array_equal(originals['R01'][0][20:30], originals['R08'][0][20:30])
        assert 'CTA' in results[-1]['plan']['retimed_subtitle_ids']
        # Rejections execute the public CLI, preserving exact project bytes.
        rejected = []
        def rejection(label, path, request, code, compose=False, digest=None):
            req = work / f'{label}.json'; save(req, request); save(public / req.name, request)
            unchanged = (path / 'project.json').read_bytes()
            flags = ['--expected-project-sha256', digest] if digest else []
            cli('timeline', 'compose' if compose else 'edit', '--project', path, '--input', req, *flags, expected=2, code=code)
            assert unchanged == (path / 'project.json').read_bytes()
            rejected.append({'case': label, 'error_code': code, 'project_bytes_unchanged': True})
        locked = copy.deepcopy(base); locked['sequences'][0]['tracks'][1]['locked'] = True
        rejection('G01-locked-link', project_at('G01', locked), {'action': 'insert', 'at_tick': TPS, 'items': items}, 'EDIT_TRACK_LOCKED')
        short = copy.deepcopy(rolling)
        for t in short['sequences'][0]['tracks']:
            for c in t['clips']:
                c.pop('presentation_window'); c['source_in_tick'] = 0; c['source_out_tick'] = c['duration_tick']
                c.pop('keyframes', None)
        rejection('G02-short-handles', project_at('G02', short), {'action': 'roll', 'left_clip_id': 'Lv', 'right_clip_id': 'Rv', 'delta_tick': TPS}, 'EDIT_RANGE_HANDLE_SHORTFALL')
        rejection('G03-stale-plan', paths['R01'], {'action': 'lift', 'at_tick': TPS, 'duration_tick': TPS,
            'track_ids': ['track_video_1']}, 'EDIT_PROJECT_CHANGED', digest=digests['R01'])
        rejection('G04-compose-rollback', paths['R01'], {'operations': [{'op': 'linked_edit', 'edit': {
            'action': 'extract', 'at_tick': TPS, 'duration_tick': TPS, 'track_ids': ['track_video_1']}},
            {'op': 'unknown_operation'}]}, 'ARGUMENT_INVALID', compose=True)
        duplicate = copy.deepcopy(items); duplicate[1]['clip']['id'] = duplicate[0]['clip']['id']
        rejection('G05-duplicate-id', seed, {'action': 'insert', 'at_tick': TPS, 'items': duplicate}, 'EDIT_RANGE_ID_CONFLICT')
        invalid = copy.deepcopy(items); invalid[0]['clip']['link_id'] = []
        rejection('G06-invalid-link', seed, {'action': 'insert', 'at_tick': TPS, 'items': invalid}, 'EDIT_RANGE_REQUEST_INVALID')
        gallery = [Image.fromarray(np.concatenate([np.concatenate([expectations[c][0][index], actuals[c][0][index]], axis=1)
            for c in ('R02', 'R06')], axis=0)) for index in range(0, 40, 2)]
        gallery[0].save(public / 'comparison.gif', save_all=True, append_images=gallery[1:],
            duration=200, loop=0, optimize=False, disposal=2)
        after = frozen()
        assert before == after
        assert old_hashes == {p.relative_to(baseline).as_posix(): sha(p) for p in baseline.rglob('*') if p.is_file()}
        save(public / 'run-state.json', {'status': 'passed', 'source_before': before, 'source_after': after, 'frozen_equal': True})
        save(public / 'verification.json', {'status': 'passed', 'fixed_original_renderer_commit': BASELINE,
            'fixed_original_renderer_sha256': old_hashes, 'source_before': before, 'source_after': after, 'frozen_equal': True,
            'cases': results, 'cli_count': len(calls), 'calls': calls, 'rejections': rejected,
            'fixed_v38_action_counterfactual_rejections': 8,
            'new_frames': sum(r['frames'] for r in results),
            'new_stereo_sample_frames': sum(r['stereo_sample_frames'] for r in results),
            'negative_controls': {'animated_picture_differs_without_motion': True, 'CTA_changes_original_pixels': True},
            'new_model_inference': 0, 'continuous_playback_or_listening': False,
            'oracle_limit': 'decoded selection from fixed same-product V38 authors; no independent retiming or image algorithm',
            'fixture_provenance': provenance,
            'files': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in public.iterdir() if p.is_file()}})
        print(json.dumps({'status': 'passed', 'cases': len(results), 'cli_count': len(calls),
            'frames': sum(r['frames'] for r in results), 'rejections': len(rejected)}))
    except Exception as exc:
        save(public / 'run-state.json', {'status': 'failed', 'source_before': before, 'source_after': frozen(),
            'error': repr(exc), 'cli_count': len(calls), 'completed_cases': len(results)})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.work.resolve())
