"""Public procedural source-handle fixtures through the actual local CLI.

Video reference for dissolve and reverse uses decoded original source frames
and independent per-pixel blend math, never the product planner/renderer.
Other transition types receive execution/window/restoration checks, not an
independent inside-window visual-quality acceptance. PCM is independently
windowed and linearly mixed for every case. Public AAC copies are previews;
float PCM/lossless render originals stay in the chosen local work directory.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'c5cffbdececb262230013a0753462a41dfb1524d'
TPS, FPS, W, H, SR = 90000, 10, 240, 136, 48000


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def digest(raw):
    return 'sha256:'+hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def frozen():
    paths = [*(ROOT/'product/src').rglob('*.py'), *(ROOT/'product/tests').rglob('*.py'),
             *(ROOT/'product/src').rglob('*.mjs'), ROOT/'docs/specs/agent-project.schema.json',
             ROOT/'product/pyproject.toml', ROOT/'product/src/ai_ad_editor/OPENFILM_LICENSE.txt']
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def run(output, work):
    import numpy as np
    from PIL import Image, ImageDraw
    output.mkdir(parents=True, exist_ok=False)
    work.mkdir(parents=True, exist_ok=False)
    before = frozen()
    def ff(args, data=None):
        return subprocess.run(['ffmpeg', '-v', 'error', '-y', '-threads', '1', *map(str, args)],
                              input=data, capture_output=True, check=True, timeout=300).stdout
    def rgb(path):
        return np.frombuffer(ff(['-i', path, '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1']), np.uint8).reshape(-1, H, W, 3)
    def pcm(path):
        return np.frombuffer(ff(['-i', path, '-vn', '-ar', SR, '-ac', 2, '-f', 'f32le', 'pipe:1']), '<f4').reshape(-1, 2)
    def encode(path, frames):
        height, width = frames.shape[1:3]
        ff(['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', FPS, '-i', 'pipe:0',
            '-an', '-c:v', 'libx264rgb', '-preset', 'ultrafast', '-crf', 0, path], frames.tobytes())
    old = work/'baseline'
    archive = subprocess.check_output(['git', '-c', 'core.autocrlf=false', 'archive', '--format=zip', BASELINE,
                                       'product/src', 'docs/specs/agent-project.schema.json'], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for item in z.infolist():
            if item.is_dir():
                continue
            path = (old/item.filename).resolve()
            assert path.is_relative_to(old.resolve())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(z.read(item))
    baseline_hashes = {p.relative_to(old).as_posix(): sha(p) for p in old.rglob('*') if p.is_file()}
    calls = []
    bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    def cli(*args, expected=0, baseline=False):
        cmd = [sys.executable, '-I', '-B', '-X', 'utf8', '-c', bootstrap,
               str(old/'product/src' if baseline else ROOT/'product/src'), *map(str, args)]
        start = time.monotonic()
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=300)
        n = len(calls)
        (work/f'{n:03}.stdout.log').write_bytes(r.stdout)
        (work/f'{n:03}.stderr.log').write_bytes(r.stderr)
        value = json.loads(r.stdout.decode('utf-8-sig')) if r.stdout.strip() else {'usage': r.stderr.decode('utf-8', 'replace')}
        calls.append({'index': n, 'args': list(map(str, args)), 'baseline': baseline, 'exit_code': r.returncode,
                      'expected_exit_code': expected, 'seconds': time.monotonic()-start,
                      'stdout_sha256': digest(r.stdout), 'stderr_sha256': digest(r.stderr)})
        save(work/'partial-calls.json', calls)
        assert r.returncode == expected, (r.returncode, value)
        return value
    cli('doctor')
    cli('capabilities')
    video_sources, audio_sources = {}, {}
    segments = ['abcedf', 'bc', 'abged', 'abgcd', 'fgbc', 'afgcd', 'afgecd', 'abc', 'abcdefg', 'abfgcd']
    bars = {'a': (2, 0, 13, 3), 'b': (12, 2, 15, 14), 'c': (12, 14, 15, 27),
            'd': (2, 25, 13, 28), 'e': (0, 14, 3, 27), 'f': (0, 2, 3, 14), 'g': (2, 12, 13, 16)}
    def number(draw, number, x, y):
        for digit in f'{number:03}':
            for bar in segments[int(digit)]:
                a,b,c,d = bars[bar]
                draw.rectangle((x+a, y+b, x+c, y+d), fill='white')
            x += 20
    for sid, phase, hz in (('a', 0, 220), ('b', 23, 420), ('c', 47, 660)):
        frames = []
        for k in range(80):
            value = 30+((k+phase)*2)%180
            frame = Image.new('RGB', (W, H), (value, value, value))
            draw = ImageDraw.Draw(frame)
            draw.rectangle((0, 0, W, 36), fill=(12, 12, 12))
            number(draw, k, 8, 4)
            number(draw, phase, 160, 4)
            x = (k*3+phase) % (W-20)
            draw.rectangle((x, 70, x+19, 115), fill=(240, 240, 240))
            frames.append(np.asarray(frame))
        path = output/f'source-{sid}.mp4'
        encode(path, np.stack(frames))
        video_sources[sid] = rgb(path)
        assert np.array_equal(video_sources[sid], np.stack(frames))
        t = np.arange(8*SR)/SR
        signal = np.stack((.12*np.sin(2*np.pi*hz*t), .09*np.sin(2*np.pi*(hz+37)*t+.2)), axis=1)
        quantized = np.rint(signal*32767).astype('<i2')
        path = output/f'sound-{sid}.wav'
        ff(['-f', 's16le', '-ar', SR, '-ac', 2, '-i', 'pipe:0', '-c:a', 'pcm_s16le', path], quantized.tobytes())
        audio_sources[sid] = pcm(path)
    provenance = {'license_spdx': 'CC0-1.0', 'description': 'Self-authored grayscale source counters, moving boxes and stereo synthetic tones; no stock media, fonts, models or services.',
                  'generator': 'scripts/smoke_source_transitions.py', 'generator_sha256': sha(Path(__file__)),
                  'source_video': {'width': W, 'height': H, 'fps': FPS, 'frames': 80, 'seconds': 8},
                  'source_audio': {'sample_rate': SR, 'channels': 2, 'samples': 8*SR, 'encoding': 'PCM16'},
                  'ffmpeg_sha256': sha(Path(shutil.which('ffmpeg'))), 'baseline_ref': BASELINE,
                  'new_model_inference': 0, 'browser_invocations': 0}
    save(output/'fixture-provenance.json', provenance)
    base = work/'base-project'
    cli('project', 'init', base)
    for sid in ('a', 'b', 'c'):
        for aid, path in ((f'video_{sid}', output/f'source-{sid}.mp4'), (f'audio_{sid}', output/f'sound-{sid}.wav')):
            cli('media', 'ingest', '--project', base, '--input', path, '--asset-id', aid,
                '--verification-status', 'verified', '--permitted-use', 'commercial_ad', '--license-spdx', 'CC0-1.0',
                '--source', 'self-authored-procedural-fixture', '--evidence', output/'fixture-provenance.json')
    author = json.loads((base/'project.json').read_text(encoding='utf-8'))
    author['settings']['canvas'].update(width=W, height=H)
    author['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
    sequence = author['sequences'][0]
    sequence.update(duration_tick=6*TPS, tracks=[])
    for kind, prefix in (('video', 'video'), ('audio', 'audio')):
        clips = []
        for i, sid in enumerate(('a', 'b', 'c')):
            clips.append({'id': f'{prefix}_{sid}_clip', 'asset_id': f'{prefix}_{sid}', 'link_id': f'group_{sid}',
                          'timeline_start_tick': i*2*TPS, 'duration_tick': 2*TPS,
                          'source_in_tick': 2*TPS, 'source_out_tick': 4*TPS})
        sequence['tracks'].append({'id': f'{kind}_track', 'kind': kind, 'order': len(sequence['tracks']), 'clips': clips})
    save(base/'project.json', author)
    save(output/'authored-project.json', author)
    shutil.copyfile(base/'rights-ledger.json', output/'rights-ledger.json')
    def render(project, name, *, baseline=False):
        target = project/'renders'/(name+'.mkv')
        response = cli('render', '--project', project, '--output', target, '--container', 'mkv', '--crf', 0,
                       '--pixel-format', 'yuv444p', '--audio-codec', 'pcm_f32le', '--publish', baseline=baseline)
        preview = output/(name+'.mp4')
        ff(['-i', target, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', preview])
        return rgb(target), pcm(target), {'local_mkv': str(target), 'sha256': sha(target),
                                       'preview': preview.name, 'preview_sha256': sha(preview), 'response': response}
    baseline_project = work/'fixed-v34-project'
    shutil.copytree(base, baseline_project)
    old_rgb, old_pcm, old_record = render(baseline_project, 'fixed-v34-input', baseline=True)
    base_rgb, base_pcm, base_record = render(base, 'authored-input')
    assert np.array_equal(old_rgb, base_rgb) and np.array_equal(old_pcm, base_pcm)
    cli('timeline', 'transition', '--help', baseline=True, expected=2)
    def request(kind='dissolve', id='tr_ab', a='a', b='b', duration=TPS, audio='linked'):
        return {'action': 'add', 'id': id, 'from_clip_id': f'video_{a}_clip', 'to_clip_id': f'video_{b}_clip',
                'type': kind, 'duration_tick': duration, 'audio': audio}
    def edit(project, req, *extra, expected=0):
        path = project/'transition-request.json'
        save(path, req)
        return cli('timeline', 'transition', '--project', project, '--input', path, *extra, expected=expected)
    catalog = ['crossfade', 'dip_black', 'wipe_right', 'wipe_up', 'wipe_down',
               'slide_left', 'slide_right', 'slide_up', 'slide_down']
    specs = [('C01', 'two-cut-dissolve'), ('C02', 'resize-wipe'), ('C03', 'dip-white'),
             ('C04', 'reverse-2x'), ('C05', 'authored-animation'), ('C06', 'remove-restores')]
    specs += [(f'C{i+7:02}', kind) for i, kind in enumerate(catalog)]
    cases, images = [], {}
    failures = []
    for cid, scenario in specs:
        project = work/cid
        shutil.copytree(base, project)
        p = copy.deepcopy(author)
        if cid == 'C04':
            for c in p['sequences'][0]['tracks'][0]['clips'][:2]:
                c.update(reverse=True, speed=2, source_out_tick=6*TPS)
        if cid == 'C05':
            b = p['sequences'][0]['tracks'][0]['clips'][1]
            b['keyframes'] = [{'property': 'transform.opacity', 'keyframes': [
                {'at_tick': 0, 'value': .3, 'interpolation': 'linear'}, {'at_tick': 2*TPS, 'value': .8, 'interpolation': 'linear'}]}]
            b['mask'] = {'type': 'rectangle', 'x': .1, 'y': .1, 'width': .8, 'height': .8}
        save(project/'project.json', p)
        before_rgb, before_pcm = base_rgb, base_pcm
        if cid in {'C04', 'C05'}:
            before_rgb, before_pcm, _ = render(project, cid+'-input')
        req = request()
        if cid == 'C03':req['type'] = 'dip_white'
        if cid == 'C04':req['audio'] = 'none'
        if cid >= 'C07':req['type'] = scenario
        dry = edit(project, req, '--dry-run')
        edit(project, req, '--expected-project-sha256', dry['data']['plan']['project_sha256'], '--idempotency-key', 'add-transition')
        replay = edit(project, req, '--expected-project-sha256', dry['data']['plan']['project_sha256'], '--idempotency-key', 'add-transition')
        assert any(w['code'] == 'IDEMPOTENT_REPLAY' for w in replay.get('warnings', []))
        if cid in {'C01', 'C06'}:
            edit(project, request(id='tr_bc', a='b', b='c'))
        if cid == 'C02':
            edit(project, {'action': 'resize', 'id': 'tr_ab', 'duration_tick': 54000, 'type': 'wipe_left'})
        if cid == 'C06':
            edit(project, {'action': 'remove', 'id': 'tr_ab'})
            edit(project, {'action': 'remove', 'id': 'tr_bc'})
        saved = json.loads((project/'project.json').read_text(encoding='utf-8'))
        seq = saved['sequences'][0]
        assert seq['tracks'] == p['sequences'][0]['tracks'] and seq['duration_tick'] == 6*TPS
        save(output/(cid+'-project.json'), saved)
        cli('validate', '--project', project, '--strict-rights')
        cli('policy', 'audit', '--project', project)
        actual_rgb, actual_pcm, render_record = render(project, cid+'-actual')
        assert len(actual_rgb) == 60 and len(actual_pcm) == 6*SR
        windows = []
        if cid != 'C06':
            d = .6 if cid == 'C02' else 1.
            windows.append((2-d/2, 2+d/2))
            if cid == 'C01':windows.append((3.5, 4.5))
        outside = [k for k in range(60) if all(not (a <= k/FPS < b) for a,b in windows)]
        outside_error = int(np.abs(actual_rgb[outside].astype(int)-before_rgb[outside].astype(int)).max())
        assert outside_error <= 1, (cid, outside_error)
        reference_pcm = np.concatenate([audio_sources[s][2*SR:4*SR] for s in ('a', 'b', 'c')]).copy()
        for window_index, (a,b) in enumerate(windows if cid != 'C04' else []):
            left_sid, right_sid = ('a', 'b') if window_index == 0 else ('b', 'c')
            start, end = round(a*SR), round(b*SR)
            n = end-start
            offset = np.arange(n)
            left_at, right_at = round((4-(b-a)/2)*SR), round((2-(b-a)/2)*SR)
            gain = offset/n
            reference_pcm[start:end] = audio_sources[left_sid][left_at+offset]*(1-gain[:,None])+audio_sources[right_sid][right_at+offset]*gain[:,None]
        pcm_error = float(np.abs(actual_pcm-reference_pcm).max())
        assert pcm_error <= 3e-7, (cid, pcm_error)
        pixel_reference = None
        if cid in {'C01', 'C04'}:
            pixel_reference = np.concatenate([video_sources[s][20:40] for s in ('a', 'b', 'c')]).astype(float)
            if cid == 'C04':
                pixel_reference[:20] = video_sources['a'][np.arange(59, 19, -2)]
                pixel_reference[20:40] = video_sources['b'][np.arange(59, 19, -2)]
            for index, (a,b) in enumerate(windows):
                left_sid, right_sid = ('a', 'b') if index == 0 else ('b', 'c')
                for k in range(round(a*FPS), round(b*FPS)):
                    local = k-round((0 if index == 0 else 2)*FPS)
                    weight = (k/FPS-a)/(b-a)
                    if cid == 'C04':
                        left_frame, right_frame = 59-2*local, 99-2*local
                    else:
                        left_frame, right_frame = 20+local, local
                    pixel_reference[k] = video_sources[left_sid][left_frame]*(1-weight)+video_sources[right_sid][right_frame]*weight
            pixel_error = int(np.abs(actual_rgb.astype(float)-pixel_reference).max())
            assert pixel_error <= 3, (cid, pixel_error)
            reference_path = output/(cid+'-independent-reference.mp4')
            encode(reference_path, np.rint(pixel_reference).clip(0,255).astype('uint8'))
        else:pixel_error = None
        if cid == 'C03':assert int(actual_rgb[20, H//2, W//2].min()) >= 245
        if cid == 'C06':
            assert np.array_equal(actual_rgb, base_rgb) and np.array_equal(actual_pcm, base_pcm)
            assert 'source_transitions' not in seq
        if cid == 'C01':
            failure = edit(project, request(id='no-room', a='a', b='b', duration=180000), expected=2)
            failures.append({'case': 'oversized-window', 'response': failure})
            failure = edit(project, {'action':'resize','id':'tr_ab','duration_tick':72000}, '--expected-project-sha256', '0'*64, expected=2)
            failures.append({'case': 'stale-hash', 'response': failure})
        case = {'id': cid, 'scenario': scenario, 'frames': len(actual_rgb), 'seconds': 6,
                'sample_frames': len(actual_pcm), 'outside_window_max_rgb_error': outside_error,
                'independent_full_rgb_max_error': pixel_error, 'independent_pcm_max_error': pcm_error,
                'decoded_rgb_sha256': digest(actual_rgb.tobytes()), 'decoded_pcm_sha256': digest(actual_pcm.tobytes()),
                'source_clips_and_duration_unchanged': True, 'render': render_record,
                'source_transition_plan': dry['data']['plan']}
        save(output/(cid+'-verification.json'), case)
        cases.append(case)
        images[cid] = (before_rgb.copy(), actual_rgb.copy())
    rows = []
    for cid in ('C01', 'C02', 'C03', 'C04'):
        rows.append(np.concatenate(images[cid], axis=2))
    comparison = np.concatenate(rows, axis=1)
    encode(output/'comparison.mp4', comparison)
    ff(['-i', output/'comparison.mp4', '-vf', 'fps=5,split[a][b];[a]palettegen[p];[b][p]paletteuse', '-loop', 0, output/'comparison.gif'])
    for k in (0, 20, 59):
        Image.fromarray(comparison[k]).save(output/f'comparison-{k:02}.png')
    with Image.open(output/'comparison.gif') as gif:
        gif_record = {'frames': gif.n_frames, 'width': gif.width, 'height': gif.height,
                      'duration_ms': sum((gif.seek(i) or gif.info.get('duration', 0)) for i in range(gif.n_frames))}
    save(output/'expected-rejections.json', failures)
    save(output/'cli-calls.json', calls)
    with zipfile.ZipFile(output/'cli-logs.zip', 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(work.glob('*.log')):z.write(path, path.name)
    after = frozen()
    assert before == after
    assert baseline_hashes == {p.relative_to(old).as_posix(): sha(p) for p in old.rglob('*') if p.is_file()}
    files = {p.relative_to(output).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(output.rglob('*')) if p.is_file()}
    record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'frozen_before': before, 'frozen_after': after,
              'frozen_equal': True, 'baseline_frozen': baseline_hashes, 'baseline_unchanged': True,
              'cases': cases, 'new_output_frames': sum(c['frames'] for c in cases),
              'new_output_sample_frames': sum(c['sample_frames'] for c in cases), 'gif': gif_record,
              'cli_count': len(calls), 'cli_success': sum(c['exit_code']==0 for c in calls),
              'expected_rejections': sum(c['exit_code']!=0 for c in calls), 'files': files,
              'fixed_v34_default_rgb_pcm_unchanged': True, 'fixed_v34': old_record, 'current_default': base_record,
              'continuous_playback_reviewed': False, 'audio_listened': False}
    save(output/'verification.json', record)
    print(json.dumps({k:v for k,v in record.items() if k in {'new_output_frames','new_output_sample_frames','gif','cli_count','cli_success','expected_rejections'}}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.work.resolve())
