"""Exercise tick-native linked edits through the local CLI with public fixtures.

The hand-authored reference changes explicit clip intervals, never imports the
planner. Its video is rendered by the same renderer, so that comparison proves
edit semantics rather than an independent raster implementation. Simple audio
is also checked against a separately summed NumPy PCM reference. AAC and GIF
are display copies only. No models, services, browser or package installs.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '92d14a6d5d6326efb7cf04ebed71804b11a0229c'
TPS, FPS, W, H, SECONDS, SR = 90000, 8, 240, 136, 5, 48000
N = FPS * SECONDS


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def frozen():
    paths = [*(ROOT/'product/src').rglob('*.py'), *(ROOT/'product/tests').rglob('*.py'),
             ROOT/'docs/specs/agent-project.schema.json', ROOT/'product/pyproject.toml',
             ROOT/'product/src/ai_ad_editor/OPENFILM_LICENSE.txt']
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def clip(cid, a, b, asset='source', **fields):
    source = a if asset == 'source' else 0
    if asset in {'voice', 'sfx', 'bed'}:
        asset = 'audio_' + asset
    return {'id': cid, 'asset_id': asset, 'timeline_start_tick': round(a*TPS), 'duration_tick': round((b-a)*TPS),
            'source_in_tick': round(source*TPS), 'source_out_tick': round((source+b-a)*TPS), **fields}


def track(tid, clips, kind='video', order=0, **fields):
    return {'id': tid, 'name': tid, 'kind': kind, 'order': order, 'clips': clips, **fields}


def authored(p, index):
    """Return fixture plus independently specified expected intervals/actions."""
    p = copy.deepcopy(p)
    seq = p['sequences'][0]
    seq['tracks'] = [track('main', [clip('a', 0, 1), clip('b', 1, 2), clip('c', 2, 3), clip('d', 3, 4)])]
    seq['editing'] = {'main_track_id': 'main'}
    seq['duration_tick'] = SECONDS*TPS
    seq['markers'] = [{'id': 'absolute_marker', 'at_tick': 2*TPS, 'name': 'absolute edit witness'}]
    seq['tracks'].append(track('bed', [clip('bed_clip', 0, SECONDS, 'bed')], 'audio', 8, locked=True))
    request = {'action': 'remove', 'clip_ids': ['b'], 'options': {'ripple': 'main'}}
    expected = {'a': ('main', 0), 'c': ('main', 1), 'd': ('main', 2), 'bed_clip': ('bed', 0)}
    removed = {'b'}
    manual_lanes = []
    subtitle_reference = None
    target_sequence = seq['id']
    deltas = None
    title = ''
    short = 0
    if index in (1, 4):
        title = 'sync remove' if index == 1 else 'sync opt-out'
        seq['tracks'] += [track('voice', [clip('voice_c', 2, 3, 'voice')], 'audio', 2, sync_lock=index != 4),
                          track('sfx', [clip('sfx_d', 3, 4, 'sfx')], 'audio', 3)]
        request['options']['sync'] = True
        expected.update(voice_c=('voice', 1 if index == 1 else 2), sfx_d=('sfx', 2))
    elif index in (2, 5):
        title = 'main riders / long bed' if index == 2 else 'collision lane / gain'
        seq['tracks'] += [track('titles', [clip('title_b', 1.25, 1.75, 'black',
                                              subtitle={'text': 'DELETE WITH B', 'style': {'font_asset_id': 'font', 'fontsize': 22}}),
                                         clip('title_d', 3.25, 3.75, 'black',
                                              subtitle={'text': 'FOLLOW D', 'style': {'font_asset_id': 'font', 'fontsize': 24}})], 'subtitle', 4)]
        request['options']['linkage'] = True
        for c in seq['tracks'][-1]['clips']:
            c.pop('asset_id')
            c['generator'] = {'type': 'text'}
        removed.add('title_b')
        expected['title_d'] = ('titles', 2.25)
        if index == 5:
            seq['tracks'] += [track('voice', [clip('anchored_voice', 0, 2.5, 'voice'), clip('rider', 3.125, 3.75, 'sfx')],
                                   'audio', 2, audio={'volume': .25}), track('wrong_bus', [], 'audio', 3, audio={'volume': 1.})]
            manual_lanes = [track('edit_lane_voice', [], 'audio', 9, audio={'volume': .25})]
            expected.update(anchored_voice=('voice', 0), rider=('edit_lane_voice', 2.125))
    elif index == 3:
        title = 'common sync shortfall'
        seq['tracks'][0]['clips'] = [clip('a', 0, 1), clip('b', 3, 4)]
        seq['tracks'] += [track('voice', [clip('crossing', .5, 2.5, 'voice'), clip('later', 3.5, 4.5, 'sfx')], 'audio', 2)]
        request = {'action': 'close_gap', 'at_tick': 2*TPS, 'options': {'sync': True}}
        expected = {'a': ('main', 0), 'b': ('main', 2), 'crossing': ('voice', .5),
                    'later': ('voice', 2.5), 'bed_clip': ('bed', 0)}
        removed = set()
        short = TPS
    elif index == 6:
        title = 'linked nested reverse / keys'
        parent = clip('complex', 2, 4, sequence_id='child', reverse=True, link_id='av',
                      transform={'scale': .75}, mask={'type': 'rectangle', 'x': .1, 'y': .1, 'width': .8, 'height': .8},
                      keyframes=[{'property': 'transform.rotation', 'keyframes': [
                          {'at_tick': 0, 'value': -10, 'interpolation': 'linear'},
                          {'at_tick': 2*TPS, 'value': 10, 'interpolation': 'linear'}]}])
        parent.pop('asset_id'); parent['source_in_tick'] = 0; parent['source_out_tick'] = 2*TPS
        seq['tracks'][0]['clips'] = [clip('a', 0, 1), parent]
        seq['tracks'].append(track('voice', [clip('paired_voice', 2, 4, 'voice', link_id='av')], 'audio', 2))
        p['sequences'].append({'id': 'child', 'name': 'child', 'duration_tick': 2*TPS,
                               'tracks': [track('child_video', [clip('child_source', 0, 2)])], 'markers': []})
        request = {'action': 'shift', 'clip_ids': ['complex'], 'delta_tick': TPS}
        expected = {'a': ('main', 0), 'complex': ('main', 3), 'paired_voice': ('voice', 3), 'bed_clip': ('bed', 0)}
        removed = set()
    elif index in (7, 8, 9):
        title = {7: 'sequence SRT / repeated shift', 8: 'clip SRT / shift', 9: 'sequence SRT / reverse parent'}[index]
        seq['tracks'][0]['clips'] = [clip('background', 0, SECONDS, 'black')]
        base = 'clip' if index == 8 else 'sequence'
        cue_asset = 'clip_cues' if index == 8 else 'sequence_cues'
        seq['tracks'].append(track('titles', [clip('file_title', 1, 3, cue_asset,
                     subtitle={'asset_time_base': base, 'style': {'font_asset_id': 'font', 'fontsize': 38}})], 'subtitle', 4))
        expected = {'background': ('main', 0), 'file_title': ('titles', 1.5), 'bed_clip': ('bed', 0)}
        removed = set()
        deltas = [TPS, -TPS//2] if index == 7 else [TPS//2]
        request = {'action': 'shift', 'clip_ids': ['file_title'], 'delta_tick': deltas[0]}
        if base == 'sequence':
            subtitle_reference = 'reference_cues'
        if index == 9:
            seq['id'] = 'child'; target_sequence = 'child'
            outer = clip('reverse_parent', 0, SECONDS, sequence_id='child', reverse=True)
            outer.pop('asset_id')
            p['sequences'].insert(0, {'id': 'seq_main', 'name': 'reverse parent', 'duration_tick': SECONDS*TPS,
                                    'tracks': [track('parent_video', [outer])], 'markers': []})
    reference = copy.deepcopy(p)
    refseq = next(s for s in reference['sequences'] if s['id'] == target_sequence)
    originals = {c['id']: copy.deepcopy(c) for t in refseq['tracks'] for c in t['clips']}
    assert set(originals) - removed == set(expected)
    refseq['tracks'].extend(manual_lanes)
    for t in refseq['tracks']:
        t['clips'] = []
    for cid, (tid, seconds) in expected.items():
        c = originals[cid]
        c['timeline_start_tick'] = round(seconds*TPS)
        if cid == 'file_title' and subtitle_reference:
            c['asset_id'] = subtitle_reference
        next(t for t in refseq['tracks'] if t['id'] == tid)['clips'].append(c)
    # Empty tracks remain authored. Only these explicit intervals are the oracle.
    return p, reference, {'id': f'L{index:02}', 'title': title, 'request': request,
                          'sequence_id': target_sequence, 'deltas': deltas,
                          'expected': {cid: [tid, round(seconds*TPS)] for cid, (tid, seconds) in expected.items()},
                          'removed': sorted(removed), 'expected_short_tick': short}


def run(output, work, font, font_license):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    if output.exists() or work.exists():
        raise ValueError('Use fresh output/work paths; preserve development failures')
    output.mkdir(parents=True); work.mkdir(parents=True)
    initial = frozen(); started = datetime.now(timezone.utc).isoformat()
    for key in ('TEMP', 'TMP', 'TMPDIR'):
        os.environ[key] = str(work)
    def ff(args, raw=None):
        r = subprocess.run(['ffmpeg', '-v', 'error', *map(str, args)], input=raw, capture_output=True, timeout=300)
        if r.returncode:
            raise RuntimeError(r.stderr.decode('utf-8', 'replace'))
        return r.stdout
    def probe(path):
        return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(path)]))
    def video(path):
        v = next(s for s in probe(path)['streams'] if s['codec_type'] == 'video')
        return np.frombuffer(ff(['-i', path, '-map', '0:v:0', '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1']), np.uint8).reshape(-1, v['height'], v['width'], 3)
    def pcm(path):
        return np.frombuffer(ff(['-i', path, '-map', '0:a:0', '-ac', 2, '-ar', SR, '-f', 'f32le', '-c:a', 'pcm_f32le', 'pipe:1']), np.float32).reshape(-1, 2)
    def encode(path, frames):
        h, w = frames.shape[1:3]
        ff(['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', FPS, '-i', 'pipe:0', '-an',
            '-c:v', 'libx264rgb', '-preset', 'ultrafast', '-crf', 0, path], frames.tobytes())
        assert np.array_equal(video(path), frames)
    old = work/'baseline'
    archive_raw = subprocess.check_output(['git', '-c', 'core.autocrlf=false', 'archive', '--format=zip', BASELINE,
                                            'product/src', 'docs/specs/agent-project.schema.json'], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as z:
        for item in z.infolist():
            if item.is_dir():
                continue
            p = (old/item.filename).resolve(); assert p.is_relative_to(old.resolve())
            p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(z.read(item))
    old_frozen = {p.relative_to(old).as_posix(): sha(p) for p in old.rglob('*') if p.is_file()}
    calls = []
    bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    def cli(*args, baseline=False, expected=0):
        command = [sys.executable, '-I', '-B', '-X', 'utf8', '-c', bootstrap,
                   str(old/'product/src' if baseline else ROOT/'product/src'), *map(str, args)]
        start = time.monotonic()
        r = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=300)
        i = len(calls)
        (work/f'call-{i:03}.stdout.log').write_bytes(r.stdout); (work/f'call-{i:03}.stderr.log').write_bytes(r.stderr)
        value = json.loads(r.stdout.decode('utf-8-sig')) if r.stdout.strip() else {'stderr': r.stderr.decode('utf-8', 'replace')}
        calls.append({'args': list(map(str, args)), 'baseline': baseline, 'exit_code': r.returncode,
                      'seconds': time.monotonic()-start, 'result': value,
                      'stdout_sha256': digest(r.stdout), 'stderr_sha256': digest(r.stderr)})
        save(work/'partial-calls.json', calls)
        assert r.returncode == expected, (r.returncode, value)
        return value
    preflight = {'doctor': cli('doctor'), 'capabilities': cli('capabilities')}
    label = ImageFont.truetype(str(font), 18)
    frames = []
    for i in range(N):
        a = Image.new('RGB', (W, H), (35+int(i//FPS)*30, 48, 100))
        d = ImageDraw.Draw(a); d.rectangle((i*5 % (W-25), 58, i*5 % (W-25)+24, 116), fill=(245, 185, 45))
        d.text((8, 9), f'SOURCE {i:02} / {i/FPS:.3f}s', font=label, fill='white')
        frames.append(np.asarray(a))
    source_frames = np.stack(frames); encode(output/'source.mp4', source_frames)
    Image.new('RGB', (W, H), 'black').save(output/'black.png')
    shutil.copyfile(font_license, output/'font-license.txt')
    sources = {}
    t = np.arange(SECONDS*SR)/SR
    for name, hz, amplitude in (('voice', 280, .15), ('sfx', 750, .12), ('bed', 110, .025)):
        samples = np.column_stack([np.sin(2*np.pi*hz*t), np.cos(2*np.pi*(hz+30)*t)])*amplitude
        quantized = np.rint(samples*32767).astype('<i2')
        ff(['-f', 's16le', '-ar', SR, '-ac', 2, '-i', 'pipe:0', '-c:a', 'pcm_s16le', output/(name+'.wav')], quantized.tobytes())
        sources[name] = quantized.astype(np.float64)/32768.
    for name, a, b in (('sequence_cues', '01,250', '01,750'), ('clip_cues', '00,250', '00,750'),
                       ('reference_cues', '01,750', '02,250')):
        (output/(name+'.srt')).write_text(f'1\n00:00:{a} --> 00:00:{b}\nLOCAL CUE\n', encoding='utf-8', newline='\n')
    provenance = {'license_spdx': 'CC0-1.0', 'description': 'Self-authored colored frame counters, synthetic sine waves, black PNG and SRT text; no third-party footage/models.',
                  'generator': 'scripts/smoke_linked_edit.py', 'generator_sha256': sha(Path(__file__)),
                  'font': {'sha256': sha(font), 'license_sha256': sha(font_license), 'binary_distributed': False},
                  'ffmpeg': {'sha256': sha(Path(shutil.which('ffmpeg'))), 'version': subprocess.check_output(['ffmpeg', '-version']).decode('utf-8', 'replace').splitlines()[0]},
                  'baseline_ref': BASELINE, 'new_model_inference': 0}
    save(output/'fixture-provenance.json', provenance)
    def independent_audio(p):
        # Only direct, normal-speed, no-effect audio exists in these fixtures.
        result = np.zeros((SECONDS*SR, 2), np.float64)
        for s in p['sequences']:
            for tr in s['tracks']:
                if tr['kind'] != 'audio' or tr.get('muted'):
                    continue
                gain = tr.get('audio', {}).get('volume', 1.)
                for c in tr['clips']:
                    n = round(c['duration_tick']/TPS*SR)
                    at = round(c['timeline_start_tick']/TPS*SR)
                    source_at = round(c['source_in_tick']/TPS*SR)
                    result[at:at+n] += sources[c['asset_id'].removeprefix('audio_')][source_at:source_at+n]*gain
        # L09's child audio is reversed by its parent.
        if p['sequences'][0]['tracks'][0]['clips'][0].get('id') == 'reverse_parent':
            result = result[::-1].copy()
        return result.astype(np.float32)
    cases = []; decoded = {}; audios = {}; restrictions = []
    asset_paths = {'source': output/'source.mp4', 'black': output/'black.png', 'font': font,
                   **{'audio_'+n: output/(n+'.wav') for n in sources},
                   **{n: output/(n+'.srt') for n in ('sequence_cues', 'clip_cues', 'reference_cues')}}
    for index in range(1, 10):
        code = f'L{index:02}'; project = work/code
        cli('project', 'init', project)
        for aid, path in asset_paths.items():
            isfont = aid == 'font'
            cli('media', 'ingest', '--project', project, '--input', path, '--asset-id', aid,
                '--verification-status', 'verified', '--permitted-use', 'commercial_ad',
                '--license-spdx', 'LicenseRef-Bitstream-Vera-DejaVu' if isfont else 'CC0-1.0',
                '--source-url', 'local://explicit-DejaVu-font' if isfont else 'local://generated-linked-edit',
                '--evidence', str(font_license) if isfont else 'local://scripts/smoke_linked_edit.py')
        p = json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
        p['settings']['canvas'].update(width=W, height=H)
        p['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
        p['settings']['output'] = {'container': 'mkv', 'video': {'codec': 'libx264', 'preset': 'ultrafast', 'crf': 0, 'pixel_format': 'yuv444p'},
                                   'audio': {'codec': 'pcm_f32le', 'bitrate': '192k'}}
        before, reference, spec = authored(p, index)
        save(project/'project.json', before); save(output/(code+'-input-project.json'), before)
        save(output/(code+'-reference-project.json'), reference); save(output/(code+'-expected.json'), spec)
        shutil.copyfile(project/'rights-ledger.json', output/(code+'-rights-ledger.json'))
        cli('validate', '--project', project, '--strict-rights')
        # Every preview/oracle starts from precisely the same authored project.
        path = project/'renders/input.mkv'; cli('render', '--project', project, '--output', path, '--publish')
        shutil.copyfile(path, output/(code+'-input.mkv'))
        shutil.copyfile(path.with_suffix('.mkv.manifest.json'), output/(code+'-input.mkv.manifest.json'))
        decoded[(code, 'input')] = video(path); audios[(code, 'input')] = pcm(path)
        if index == 1:
            oldpath = project/'renders/v32-control.mkv'
            cli('render', '--project', project, '--output', oldpath, '--publish', baseline=True)
            assert np.array_equal(video(oldpath), decoded[(code, 'input')])
            assert np.array_equal(pcm(oldpath), audios[(code, 'input')])
            shutil.copyfile(oldpath, output/'L01-v32-control.mkv')
        request_path = work/(code+'-edit.json'); save(request_path, spec['request'])
        # Dry-run must leave every project file, including prior renders, intact.
        filetree = lambda: {p.relative_to(project).as_posix(): sha(p) for p in project.rglob('*') if p.is_file()}
        tree = filetree()
        args = ('timeline', 'edit', '--project', project, '--input', request_path, '--sequence-id', spec['sequence_id'])
        dry = cli(*args, '--dry-run'); assert tree == filetree()
        if index == 1:
            reject = cli(*args, baseline=True, expected=2)
            assert tree == filetree()
            restrictions.append({'kind': 'fixed-V32-command-unavailable', 'result': reject, 'project_unchanged': True})
        base_hash = dry['data']['plan']['base_project_sha256']
        result = cli(*args, '--expected-project-sha256', base_hash, '--idempotency-key', code)
        saved = json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
        assert result['data']['plan']['short_tick'] == spec['expected_short_tick']
        snapshot_tree = filetree()
        replay = cli(*args, '--expected-project-sha256', base_hash, '--idempotency-key', code)
        assert result['operation_id'] == replay['operation_id'] and snapshot_tree == filetree()
        stale = cli(*args, '--expected-project-sha256', base_hash, expected=2)
        assert stale['errors'][0]['code'] == 'EDIT_PROJECT_CHANGED' and snapshot_tree == filetree()
        plans = [result['data']['plan']]
        if spec['deltas'] and len(spec['deltas']) > 1:
            save(request_path, {**spec['request'], 'delta_tick': spec['deltas'][1]})
            plans.append(cli(*args)['data']['plan'])
            saved = json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
        save(output/(code+'-actual-project.json'), saved); save(output/(code+'-plans.json'), plans)
        actualseq = next(s for s in saved['sequences'] if s['id'] == spec['sequence_id'])
        positions = {c['id']: [t['id'], c['timeline_start_tick']] for t in actualseq['tracks'] for c in t['clips']}
        assert positions == spec['expected'], (code, positions, spec['expected'])
        originalseq = next(s for s in before['sequences'] if s['id'] == spec['sequence_id'])
        assert actualseq['markers'] == originalseq['markers']
        assert next(t for t in actualseq['tracks'] if t['id'] == 'bed') == next(t for t in originalseq['tracks'] if t['id'] == 'bed')
        for variant, model in (('after', saved), ('reference', reference)):
            save(project/'project.json', model)
            path = project/f'renders/{variant}.mkv'
            rendered = cli('render', '--project', project, '--output', path, '--publish')
            shutil.copyfile(path, output/(code+'-'+variant+'.mkv'))
            shutil.copyfile(path.with_suffix('.mkv.manifest.json'), output/(code+'-'+variant+'.mkv.manifest.json'))
            decoded[(code, variant)] = video(path); audios[(code, variant)] = pcm(path)
            assert decoded[(code, variant)].shape == (N, H, W, 3)
            assert audios[(code, variant)].shape == (SECONDS*SR, 2)
        save(project/'project.json', saved)
        assert np.array_equal(decoded[(code, 'after')], decoded[(code, 'reference')]), code+' video differs'
        samples = independent_audio(reference); samples_before = independent_audio(before)
        error = np.abs(audios[(code, 'after')].astype(np.float64)-samples)
        before_error = np.abs(audios[(code, 'input')].astype(np.float64)-samples_before)
        assert max(float(error.max()), float(before_error.max())) <= 2e-6, (code, error.max(), before_error.max())
        ff(['-f', 'f32le', '-ar', SR, '-ac', 2, '-i', 'pipe:0', '-c:a', 'pcm_f32le', output/(code+'-reference.wav')], samples.tobytes())
        assert np.array_equal(pcm(output/(code+'-reference.wav')), samples)
        for variant in ('input', 'after', 'reference'):
            ff(['-i', output/(code+'-'+variant+'.mkv'), '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'copy',
                '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', output/(code+'-'+variant+'.mp4')])
        quality = cli('quality', 'check', '--project', project, '--input', project/'renders/after.mkv', '--require-audio')
        policy = cli('policy', 'audit', '--project', project)
        if index in (5, 7):
            package = project/'exports'/f'{code}.aevpkg.zip'
            cli('convert', 'export', '--project', project, '--target-format', 'package', '--output', package)
            shutil.copyfile(package, output/(code+'.aevpkg.zip'))
        record = {**spec, 'plans': plans, 'dry_run': dry, 'formal_result': result, 'quality': quality, 'policy': policy,
                  'dry_run_read_only': True, 'idempotent_replay_read_only': True, 'stale_plan_rejected_read_only': True,
                  'exact_manual_positions': True, 'locked_track_and_absolute_markers_unchanged': True,
                  'frames_per_variant': N, 'fps': FPS, 'seconds': SECONDS, 'channels': 2, 'sample_rate': SR,
                  'video_equals_manual_reference': True, 'decoded_rgb_sha256': digest(decoded[(code, 'after')].tobytes()),
                  'audio_sample_frames_per_variant': SECONDS*SR, 'max_pcm_sample_error': float(error.max()),
                  'input_max_pcm_sample_error': float(before_error.max()), 'audio_gate': 2e-6,
                  'decoded_pcm_sha256': digest(audios[(code, 'after')].tobytes()),
                  'reference_pcm_sha256': digest(samples.tobytes()),
                  'reference_scope': 'Explicit hand-authored positions and rewritten SRT; same raster renderer. Direct simple audio additionally uses independent NumPy mixing, not perceptual quality.',
                  'outputs': {p.name: {'sha256': sha(p), 'probe': probe(p)} for p in sorted(output.glob(code+'-*')) if p.suffix in {'.mkv', '.mp4', '.wav'}}}
        save(output/(code+'-verification.json'), record); cases.append(record)
        print(json.dumps({'case': code, 'video_equal': True, 'max_audio_error': float(error.max()), 'short_tick': plans[0]['short_tick']}, ensure_ascii=False), flush=True)
    # Three columns deliberately say input, not old failure: this is a new API.
    chosen = ('L01', 'L02', 'L05', 'L07')
    header, row_h = 44, H+98
    small = ImageFont.truetype(str(font), 13); heading = ImageFont.truetype(str(font), 15)
    preview = []
    for i in range(N):
        image = Image.new('RGB', (3*W, header+len(chosen)*row_h), (20, 24, 32)); d = ImageDraw.Draw(image)
        for col, name in enumerate(('Authored input', 'CLI edited actual', 'Manual timeline reference')):
            d.text((col*W+6, 12), name, font=heading, fill='white')
        for row, code in enumerate(chosen):
            y = header+row*row_h
            spec = next(c for c in cases if c['id'] == code)
            for col, variant in enumerate(('input', 'after', 'reference')):
                x = col*W
                text = code+' '+spec['title']; textfont = small
                while d.textbbox((0, 0), text, font=textfont)[2] > W-12:
                    textfont = ImageFont.truetype(str(font), textfont.size-1)
                d.text((x+6, y+3), text, font=textfont, fill='white')
                image.paste(Image.fromarray(decoded[(code, variant)][i]), (x, y+24))
                a = audios[(code, variant)]
                for ch, color in ((0, (60, 220, 150)), (1, (85, 145, 255))):
                    cy = y+H+40+ch*24
                    d.line((x, cy, x+W-1, cy), fill=(70, 80, 90))
                    for px in range(W):
                        part = a[px*len(a)//W:(px+1)*len(a)//W, ch]
                        d.line((x+px, cy-float(part.max())*65, x+px, cy-float(part.min())*65), fill=color)
                    d.line((x+round(i/N*W), cy-11, x+round(i/N*W), cy+11), fill='white')
                d.text((x+5, y+H+78), '5 s | L/R PCM | silent preview', font=small, fill='white')
        preview.append(image)
    preview[0].save(output/'comparison-first.png'); preview[-1].save(output/'comparison-last.png')
    preview[0].save(output/'comparison.gif', save_all=True, append_images=preview[2::2], duration=250, loop=0, optimize=False, disposal=2)
    encode(output/'comparison.mp4', np.stack([np.asarray(im) for im in preview]))
    gif_durations = []
    with Image.open(output/'comparison.gif') as im:
        for i in range(im.n_frames):
            im.seek(i); gif_durations.append(im.info.get('duration', 0))
    assert frozen() == initial
    assert old_frozen == {p.relative_to(old).as_posix(): sha(p) for p in old.rglob('*') if p.is_file() and '.runtime' not in p.relative_to(old).parts}
    record = {'started_at_utc': started, 'finished_at_utc': datetime.now(timezone.utc).isoformat(),
              'frozen_before': initial, 'frozen_after': frozen(), 'frozen_file_count': len(initial),
              'baseline_ref': BASELINE, 'baseline_control_pixel_and_pcm_equal': True,
              'cases': cases, 'case_count': len(cases), 'content_passed_cases': len(cases),
              'new_output_frames': N*len(cases), 'input_frames': N*len(cases), 'manual_reference_frames': N*len(cases),
              'new_output_stereo_sample_frames': SECONDS*SR*len(cases),
              'cli_calls': calls, 'cli_count': len(calls), 'expected_rejections': sum(c['exit_code'] != 0 for c in calls),
              'preflight': preflight, 'restrictions': restrictions, 'provenance': provenance,
              'browser_opened': False, 'new_model_inference': 0, 'continuous_playback_review': False, 'listening_review': False,
              'preview': {'mp4_probe': probe(output/'comparison.mp4'), 'gif_encoded_frames': len(gif_durations), 'gif_duration_ms': sum(gif_durations)},
              'public_files': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}}
    save(output/'verification.json', record)
    print(json.dumps({k: record[k] for k in ('case_count', 'content_passed_cases', 'cli_count', 'expected_rejections', 'new_output_frames', 'frozen_file_count')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('output', 'work', 'font', 'font-license'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.work.resolve(), args.font.resolve(), args.font_license.resolve())
