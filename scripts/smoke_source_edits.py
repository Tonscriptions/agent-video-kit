"""Actual offline source edits versus manually authored, fixed V39 renders.

The comparison is a compatibility oracle for planning, not an independent
retiming/quality renderer. Two plain cases additionally identify decoded
source frames without consulting either planner or the reference timeline.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import queue
from pathlib import Path
import shutil
import subprocess
import sys
import time
import threading
import zipfile

from smoke_fragments import frozen, save, sha

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '78e9c4bdd7b8d199ab6e0b268b7edd0790480c7b'
TPS, FPS, W, H, SR = 90000, 10, 240, 136, 48000


def run(public, work):
    import numpy as np
    from PIL import Image

    public.mkdir(parents=True, exist_ok=False)
    work.mkdir(parents=True, exist_ok=False)
    before, calls, rows = frozen(), [], []
    save(public/'run-state.json', {'status': 'running', 'source_before': before})
    baseline = work/'fixed-v39'
    archive = subprocess.check_output(['git', '-c', 'core.autocrlf=false', 'archive', '--format=zip',
                                      BASELINE, 'product/src', 'docs/specs/agent-project.schema.json'], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for entry in z.infolist():
            if entry.is_dir():
                continue
            path = (baseline/entry.filename).resolve()
            assert path.is_relative_to(baseline.resolve())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(z.read(entry))
    old_hashes = {p.relative_to(baseline).as_posix(): sha(p) for p in baseline.rglob('*') if p.is_file()}
    boot = '''import contextlib,io,json,sys,traceback
sys.path.insert(0,sys.argv.pop(1))
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
from ai_ad_editor.cli import main
channel=sys.stdout
for line in sys.stdin:
    output,errors=io.StringIO(),io.StringIO()
    with contextlib.redirect_stdout(output),contextlib.redirect_stderr(errors):
        try: code=main(json.loads(line))
        except SystemExit as exc: code=exc.code or 0
        except BaseException:
            traceback.print_exc();code=1
    channel.write(json.dumps({'exit_code':code,'stdout':output.getvalue(),'stderr':errors.getvalue()},ensure_ascii=True)+'\\n')
    channel.flush()
'''
    workers = {}

    def worker(old):
        if old not in workers:
            errors = (public/('worker-v39.stderr.log' if old else 'worker-current.stderr.log')).open('wb')
            process = subprocess.Popen([sys.executable, '-E', '-B', '-X', 'utf8', '-c', boot,
                str(baseline/'product/src' if old else ROOT/'product/src')], cwd=ROOT,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                text=True, encoding='utf-8', bufsize=1)
            replies = queue.Queue()
            def read():
                for line in process.stdout:
                    replies.put(line)
                replies.put(None)
            threading.Thread(target=read, daemon=True).start()
            workers[old] = (process, replies, errors)
        return workers[old]

    def close_workers():
        for process, _, errors in workers.values():
            if process.poll() is None:
                process.stdin.close()
                try: process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=10)
            errors.close()

    def cli(*args, old=False, expected=0, code=None):
        started = time.monotonic()
        process, replies, _ = worker(old)
        process.stdin.write(json.dumps(list(map(str, args)), ensure_ascii=True)+'\n'); process.stdin.flush()
        reply = replies.get(timeout=300)
        assert reply is not None, 'CLI worker exited before producing a response'
        response = json.loads(reply)
        stdout, stderr = response['stdout'].encode('utf-8'), response['stderr'].encode('utf-8')
        index = len(calls)
        for label, raw in [('stdout', stdout), ('stderr', stderr)]:
            (public/f'cli-{index:03}-{label}.log').write_bytes(raw)
        result = json.loads(stdout.decode('utf-8-sig'))
        calls.append({'index': index, 'args': list(map(str, args)), 'fixed_v39': old,
            'exit_code': response['exit_code'], 'expected_exit_code': expected, 'expected_error_code': code,
            'execution': 'native-persistent-cli-main', 'worker_pid': process.pid,
            'seconds': time.monotonic()-started, 'stdout_sha256': sha(public/f'cli-{index:03}-stdout.log'),
            'stderr_sha256': sha(public/f'cli-{index:03}-stderr.log')})
        save(public/'calls-in-progress.json', calls)
        assert response['exit_code'] == expected, result
        if code:
            assert result['errors'][0]['code'] == code, result
        return result

    def ff(args):
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-nostdin', '-filter_complex_threads', '1',
                        *map(str, args)], check=True, capture_output=True, timeout=180)

    def decode(path):
        picture = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
                         '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'])
        sound = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
                         '-vn', '-ac', '2', '-ar', str(SR), '-f', 'f32le', 'pipe:1'])
        return (np.frombuffer(picture, np.uint8).reshape(-1, H, W, 3),
                np.frombuffer(sound, '<f4').reshape(-1, 2))

    pictures, original_pictures, cases = {}, {}, []
    seed = work/'seed'
    try:
        provenance = {'license_spdx': 'CC0-1.0', 'source': 'Original V35 synthetic counter and sound',
                      'new_model_inference': 0, 'network_runtime': False, 'virtualization': False,
                      'files': {}}
        for name in ('source-a.mp4', 'sound-a.wav'):
            path = ROOT/'docs/assets/source-transitions-20261017'/name
            shutil.copyfile(path, public/name)
            provenance['files'][name] = {'original': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}
        save(public/'fixture-provenance.json', provenance)
        cli('project', 'init', seed)
        for aid, name in [('video', 'source-a.mp4'), ('audio', 'sound-a.wav')]:
            cli('media', 'ingest', '--project', seed, '--input', public/name, '--asset-id', aid,
                '--verification-status', 'verified', '--license-spdx', 'CC0-1.0',
                '--permitted-use', 'commercial_ad', '--evidence', public/'fixture-provenance.json')
        original = json.loads((seed/'project.json').read_text(encoding='utf-8'))
        original['settings']['canvas'] = {'width': W, 'height': H}
        original['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
        original['sequences'][0]['duration_tick'] = 6*TPS

        def base():
            value = copy.deepcopy(original)
            for t, aid, cid in zip(value['sequences'][0]['tracks'], ('video', 'audio'), ('v', 'a')):
                t['clips'] = [{'id': cid, 'asset_id': aid, 'link_id': 'av', 'timeline_start_tick': TPS,
                    'duration_tick': 4*TPS, 'source_in_tick': 2*TPS, 'source_out_tick': 6*TPS}]
            return value

        def all_clips(value):
            return [c for t in value['sequences'][0]['tracks'] for c in t['clips']]

        def full_window(c):
            c['presentation_window'] = {'version': 1, 'authored_start_tick': c['timeline_start_tick'],
                'authored_duration_tick': c['duration_tick'], 'offset_tick': 0}

        def put(name, value):
            path = work/name
            shutil.copytree(seed, path)
            save(path/'project.json', value)
            save(public/(name+'-project.json'), value)
            return path

        def render(path, name, old=False):
            movie = path/'renders'/(name+'.mkv')
            result = cli('render', '--project', path, '--output', movie, '--container', 'mkv', '--crf', 0,
                '--pixel-format', 'yuv444p', '--audio-codec', 'pcm_f32le', '--publish', old=old)
            shutil.copyfile(movie, public/(name+'.mkv'))
            ff(['-i', movie, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', public/(name+'.mp4')])
            save(public/(name+'-render.json'), result)
            return decode(movie)

        def case(name, value, request, expected):
            path = put(name+'-before', value)
            prior = render(path, name+'-original', old=True)
            reference = render(put(name+'-reference', expected), name+'-expected', old=True)
            req = work/(name+'-request.json'); save(req, request); save(public/req.name, request)
            old_code = 'EDIT_RANGE_REQUEST_INVALID' if request['action'] in {'roll', 'slide'} else 'EDIT_REQUEST_INVALID'
            raw_before = (path/'project.json').read_bytes()
            cli('timeline', 'edit', '--project', path, '--input', req, '--dry-run', old=True, expected=2, code=old_code)
            preview = cli('timeline', 'edit', '--project', path, '--input', req, '--dry-run')
            assert raw_before == (path/'project.json').read_bytes()
            digest = preview['data']['plan']['base_project_sha256']
            cli('timeline', 'edit', '--project', path, '--input', req,
                '--expected-project-sha256', digest, '--idempotency-key', name)
            applied = (path/'project.json').read_bytes()
            cli('timeline', 'edit', '--project', path, '--input', req,
                '--expected-project-sha256', digest, '--idempotency-key', name)
            assert applied == (path/'project.json').read_bytes()
            cli('validate', '--project', path, '--strict-rights')
            actual = render(path, name+'-actual')
            assert actual[0].shape == reference[0].shape and actual[1].shape == reference[1].shape
            pixel = np.abs(actual[0].astype(np.int16)-reference[0].astype(np.int16))
            sound = np.abs(actual[1]-reference[1])
            row = {'case': name, 'action': request['action'], 'frames': len(actual[0]),
                'stereo_sample_frames': len(actual[1]), 'max_rgb_difference': int(pixel.max()),
                'max_pcm_difference': float(sound.max()), 'plan': preview['data']['plan'],
                'rgb_sha256': 'sha256:'+hashlib.sha256(actual[0].tobytes()).hexdigest(),
                'pcm_sha256': 'sha256:'+hashlib.sha256(actual[1].tobytes()).hexdigest(),
                'status': 'passed' if not pixel.any() and not sound.any() else 'failed'}
            rows.append(row); save(public/(name+'-verification.json'), row)
            assert row['status'] == 'passed', {k: row[k] for k in ('case', 'max_rgb_difference', 'max_pcm_difference')}
            save(public/(name+'-actual-project.json'), json.loads(applied.decode('utf-8')))
            pictures[name], original_pictures[name] = (reference[0], actual[0]), prior[0]
            cases.append((name, path, req, digest))

        value = base(); expected = copy.deepcopy(value)
        for c in all_clips(expected): c.update(source_in_tick=3*TPS, source_out_tick=7*TPS)
        case('S01', value, {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': TPS}, expected)

        expected = base()
        for c in all_clips(expected):
            c.update(timeline_start_tick=0, duration_tick=6*TPS, source_in_tick=TPS, source_out_tick=7*TPS)
            full_window(c)
        case('S02', base(), {'action': 'extend_source', 'clip_id': 'v', 'head_tick': TPS, 'tail_tick': TPS}, expected)

        value = base()
        for c in all_clips(value): c.update(reverse=True, speed=2, duration_tick=2*TPS)
        expected = copy.deepcopy(value)
        for c in all_clips(expected):
            c.update(timeline_start_tick=TPS//2, duration_tick=3*TPS, source_in_tick=TPS, source_out_tick=7*TPS)
            full_window(c)
        case('S03', value, {'action': 'extend_source', 'clip_id': 'v', 'head_tick': TPS//2, 'tail_tick': TPS//2}, expected)

        value = base()
        for c in all_clips(value): c.update(duration_tick=5*TPS, freeze={'at_tick': TPS, 'duration_tick': TPS, 'audio': 'silence'})
        all_clips(value)[0]['effects'] = [{'type': 'brightness', 'parameters': {'brightness': 0},
            'keyframes': [{'property': 'brightness', 'keyframes': [{'at_tick': 0, 'value': 0, 'interpolation': 'linear'},
                {'at_tick': 4*TPS, 'value': .2, 'interpolation': 'linear'}]}]}]
        expected = copy.deepcopy(value); expected['sequences'][0]['duration_tick'] = 13*TPS//2
        for c in all_clips(expected):
            c.update(timeline_start_tick=TPS//2, duration_tick=6*TPS, source_in_tick=3*TPS//2, source_out_tick=13*TPS//2)
            c['freeze']['at_tick'] = 3*TPS//2; full_window(c)
        keys = all_clips(expected)[0]['effects'][0]['keyframes'][0]['keyframes']
        keys[0]['at_tick'], keys[1]['at_tick'] = TPS//2, 9*TPS//2
        case('S04', value, {'action': 'extend_source', 'clip_id': 'v', 'head_tick': TPS//2, 'tail_tick': TPS//2}, expected)

        value = base()
        curve = [{'at_tick': 0, 'speed': .5, 'interpolation': 'bezier', 'control_points': [.2, .05, .7, .9]},
                 {'at_tick': 4*TPS, 'speed': 1.5, 'interpolation': 'linear'}]
        for c in all_clips(value): c.update(reverse=True, duration_tick=3*TPS, speed_curve=copy.deepcopy(curve))
        expected = copy.deepcopy(value)
        for c in all_clips(expected):
            c.update(timeline_start_tick=TPS//2, duration_tick=9*TPS//2, source_out_tick=27*TPS//4)
            c['speed_curve'][-1]['interpolation'] = 'hold'
            c['speed_curve'].append({'at_tick': 19*TPS//4, 'speed': 1.5, 'interpolation': 'hold'})
            full_window(c)
        case('S05', value, {'action': 'extend_source', 'clip_id': 'v', 'head_tick': TPS//2, 'tail_tick': TPS}, expected)

        def nested():
            value = base(); child = copy.deepcopy(value['sequences'][0])
            child.update(id='child', duration_tick=8*TPS)
            for i, t in enumerate(child['tracks']):
                t['id'] = 'child'+str(i)
                t['clips'][0].update(id='child'+str(i)+'c', timeline_start_tick=0, duration_tick=8*TPS,
                                    source_in_tick=0, source_out_tick=8*TPS, link_id='childav')
                if t['kind'] == 'audio': t['clips'][0]['audio'] = {'volume': .75}
            value['sequences'].append(child)
            value['sequences'][0]['tracks'][0]['clips'] = [{'id': 'v', 'sequence_id': 'child',
                'timeline_start_tick': TPS, 'duration_tick': 4*TPS, 'source_in_tick': 2*TPS, 'source_out_tick': 6*TPS}]
            value['sequences'][0]['tracks'][1]['clips'] = []
            return value
        value = nested(); expected = copy.deepcopy(value)
        c = all_clips(expected)[0]
        c.update(timeline_start_tick=0, duration_tick=6*TPS, source_in_tick=TPS, source_out_tick=7*TPS); full_window(c)
        case('S06', value, {'action': 'extend_source', 'clip_id': 'v', 'head_tick': TPS, 'tail_tick': TPS}, expected)

        value = base(); value['sequences'][0]['duration_tick'] = 4*TPS
        for t, aid, suffix in zip(value['sequences'][0]['tracks'], ('video', 'audio'), ('v', 'a')):
            t['clips'] = [{'id': 'l'+suffix, 'asset_id': aid, 'link_id': 'left', 'timeline_start_tick': 0,
                'duration_tick': 2*TPS, 'source_in_tick': TPS, 'source_out_tick': 3*TPS},
                {'id': 'r'+suffix, 'asset_id': aid, 'link_id': 'right', 'timeline_start_tick': 2*TPS,
                 'duration_tick': 2*TPS, 'source_in_tick': 4*TPS, 'source_out_tick': 6*TPS}]
        expected = copy.deepcopy(value)
        for t in expected['sequences'][0]['tracks']:
            l, r = t['clips']; l.update(duration_tick=5*TPS//2, source_out_tick=7*TPS//2); full_window(l)
            r['presentation_window'] = {'version': 1, 'authored_start_tick': 2*TPS,
                                        'authored_duration_tick': 2*TPS, 'offset_tick': TPS//2}
            r.update(timeline_start_tick=5*TPS//2, duration_tick=3*TPS//2)
        case('S07', value, {'action': 'roll', 'left_clip_id': 'lv', 'right_clip_id': 'rv',
                           'delta_tick': TPS//2, 'handle_policy': 'source'}, expected)

        value = base(); value['sequences'][0]['duration_tick'] = 4*TPS
        for t, aid, suffix in zip(value['sequences'][0]['tracks'], ('video', 'audio'), ('v', 'a')):
            t['clips'] = [{'id': 'l'+suffix, 'asset_id': aid, 'link_id': 'left', 'timeline_start_tick': 0,
                'duration_tick': 3*TPS//2, 'source_in_tick': TPS, 'source_out_tick': 5*TPS//2},
                {'id': 'm'+suffix, 'asset_id': aid, 'link_id': 'mid', 'timeline_start_tick': 3*TPS//2,
                 'duration_tick': TPS, 'source_in_tick': 5*TPS, 'source_out_tick': 6*TPS, 'reverse': True},
                {'id': 'r'+suffix, 'asset_id': aid, 'link_id': 'right', 'timeline_start_tick': 5*TPS//2,
                 'duration_tick': 3*TPS//2, 'source_in_tick': 2*TPS, 'source_out_tick': 7*TPS//2}]
        expected = copy.deepcopy(value)
        for t in expected['sequences'][0]['tracks']:
            l, m, r = t['clips']; full_window(l); l['duration_tick'] = TPS
            m['timeline_start_tick'] = TPS
            r.update(timeline_start_tick=2*TPS, duration_tick=2*TPS, source_in_tick=3*TPS//2); full_window(r)
        case('S08', value, {'action': 'slide', 'clip_id': 'mv', 'delta_tick': -TPS//2, 'handle_policy': 'source'}, expected)

        value = nested(); all_clips(value)[0]['speed_curve'] = [{'at_tick': 0, 'speed': 2}, {'at_tick': 4*TPS, 'speed': 2}]
        expected = copy.deepcopy(value); c = all_clips(expected)[0]
        c.update(duration_tick=5*TPS, source_out_tick=8*TPS)
        c['speed_curve'][-1]['interpolation'] = 'hold'
        c['speed_curve'].append({'at_tick': 6*TPS, 'speed': 2, 'interpolation': 'hold'}); full_window(c)
        case('S09', value, {'action': 'extend_source', 'clip_id': 'v', 'tail_tick': TPS}, expected)
        assert rows[-1]['plan']['warnings'][0]['code'] == 'SOURCE_EDIT_NESTED_CURVE_RENORMALIZED'

        gates = []
        for name, value, request, code in [
            ('G01', base(), {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': 7*TPS}, 'SOURCE_EDIT_HANDLE_SHORTFALL'),
            ('G02', base(), {'action': 'extend_source', 'clip_id': 'v', 'head_tick': 2*TPS}, 'EDIT_RANGE_EMPTY_SIDE'),
        ]:
            path = put(name, value); req = work/(name+'.json'); save(req, request)
            prior = (path/'project.json').read_bytes()
            cli('timeline', 'edit', '--project', path, '--input', req, expected=2, code=code)
            assert prior == (path/'project.json').read_bytes(); gates.append({'id': name, 'code': code, 'project_bytes_unchanged': True})
        path, req, digest = cases[0][1:]
        prior = (path/'project.json').read_bytes()
        cli('timeline', 'edit', '--project', path, '--input', req, '--expected-project-sha256', digest,
            expected=2, code='EDIT_PROJECT_CHANGED')
        batch = work/'rollback.json'; save(batch, {'operations': [
            {'op': 'linked_edit', 'edit': {'action': 'extend_source', 'clip_id': 'v', 'tail_tick': TPS//2}},
            {'op': 'linked_edit', 'edit': {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': 100*TPS}}]})
        cli('timeline', 'compose', '--project', path, '--input', batch, expected=2, code='SOURCE_EDIT_HANDLE_SHORTFALL')
        assert prior == (path/'project.json').read_bytes()

        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(public/'source-a.mp4'),
                                      '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'])
        source = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
        keys = source[:, ::8, ::8, :].reshape(len(source), -1).astype(np.float32)
        identities = []
        for name, first, last, expected_first in [('S01', 10, 50, 30), ('S02', 0, 60, 10)]:
            query = pictures[name][1][first:last, ::8, ::8, :].reshape(last-first, -1).astype(np.float32)
            distance = np.mean((query[:, None, :]-keys[None, :, :])**2, axis=2)
            found = distance.argmin(axis=1)
            expected = np.arange(expected_first, expected_first+last-first)
            row = {'case': name, 'actual_source_frame_ids': found.tolist(), 'expected_source_frame_ids': expected.tolist(),
                   'mismatches': int(np.count_nonzero(found != expected)), 'method': 'nearest-decoded-source-grid-RGB;no-timeline-or-planner'}
            identities.append(row); assert row['mismatches'] == 0, row
        save(public/'source-frame-identities.json', identities)

        frames = []
        for index in range(20):
            panel = Image.new('RGB', (W*2, H*2))
            for row, name in enumerate(('S02', 'S07')):
                reference, actual = pictures[name]
                frame = index*2
                panel.paste(Image.fromarray(reference[frame]), (0, row*H))
                panel.paste(Image.fromarray(actual[frame]), (W, row*H))
            frames.append(panel)
        frames[0].save(public/'comparison.gif', save_all=True, append_images=frames[1:], duration=200, loop=0)
        for index in (0, 6, 12, 19): frames[index].save(public/f'comparison-{index:02}.png')
        ff(['-i', public/'comparison.gif', '-vf', 'format=yuv420p', '-movflags', '+faststart', public/'comparison.mp4'])
        close_workers()
        after = frozen(); assert before == after
        record = {'status': 'passed', 'source_before': before, 'source_after': after, 'source_unchanged': True,
            'baseline': BASELINE, 'baseline_files': old_hashes, 'case_count': len(rows), 'cases': rows,
            'cli_count': len(calls), 'cli_calls': calls, 'gates': gates, 'source_frame_identities': identities,
            'output_frames': sum(r['frames'] for r in rows),
            'output_stereo_sample_frames': sum(r['stereo_sample_frames'] for r in rows),
            'compatibility_reference': 'manually authored fixed V39 projects; same renderer, not an independent quality oracle',
            'cli_execution': 'Two native Python workers import actual current/fixed CLI main once; each recorded argv calls main. These are CLI entry calls, not fresh processes per command.',
            'worker_processes_exited': all(p.poll() is not None for p, _, _ in workers.values()),
            'new_model_calls': 0, 'browser_started': False, 'continuous_playback_reviewed': False, 'listening_reviewed': False,
            'generator_sha256': sha(Path(__file__)),
            'files': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in public.iterdir() if p.is_file()}}
        save(public/'verification.json', record)
        print(json.dumps({k: record[k] for k in ('status', 'case_count', 'cli_count', 'output_frames', 'output_stereo_sample_frames')}))
    except BaseException as exc:
        save(public/'failure.json', {'error': repr(exc), 'cli_calls': calls, 'cases': rows,
                                    'source_before': before, 'source_after': frozen()})
        raise
    finally:
        close_workers()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.work.resolve())
