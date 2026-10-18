"""Real native CLI library reuse against manually authored fixed V36 projects.

Source counters/audio are byte-verified CC0 V35 fixtures. A tiny original grid
font and LUT are generated locally; no proprietary font file is redistributed.
"""
from __future__ import annotations
import argparse, copy, hashlib, io, json, shutil, subprocess, sys, time, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '19ddfb62ae710a299c403a2f93c16155138c9e76'
TPS, FPS, W, H, SR = 90000, 10, 240, 136, 48000

def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')

def frozen():
    paths = [*(ROOT/'product/src').rglob('*.py'), *(ROOT/'product/tests').rglob('*.py'),
             *(ROOT/'product/src').rglob('*.mjs'), ROOT/'product/pyproject.toml',
             ROOT/'docs/specs/agent-project.schema.json', *(ROOT/'product/src').rglob('*.json'),
             *(ROOT/'product/src').rglob('*LICENSE*.txt'), *(ROOT/'product/offline').glob('*.py')]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}

def grid_font(path):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    # Original rectangular grid drawings authored for this fixture, CC0.
    rows = {'C': ['01110','10001','10000','10000','10000','10001','01110'],
            'T': ['11111','00100','00100','00100','00100','00100','00100'],
            'A': ['00100','01010','10001','10001','11111','10001','10001'],
            'E': ['11111','10000','10000','11110','10000','10000','11111'],
            'D': ['11110','10001','10001','10001','10001','10001','11110'],
            'I': ['11111','00100','00100','00100','00100','00100','11111'],
            'V': ['10001','10001','10001','10001','10001','01010','00100'],
            '2': ['01110','10001','00001','00010','00100','01000','11111']}
    glyphs = {}
    for ch, lines in {'.notdef': ['11111']*7, 'space': ['00000']*7, **rows}.items():
        pen = TTGlyphPen(None)
        for y, line in enumerate(lines):
            for x, bit in enumerate(line):
                if bit == '1':
                    left, bottom = 40+100*x, 100*(6-y)
                    pen.moveTo((left, bottom)); pen.lineTo((left+90, bottom)); pen.lineTo((left+90, bottom+90))
                    pen.lineTo((left, bottom+90)); pen.closePath()
        glyphs[ch] = pen.glyph()
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(glyphs)); fb.setupCharacterMap({32: 'space', **{ord(ch): ch for ch in rows}})
    fb.setupGlyf(glyphs); fb.setupHorizontalMetrics({ch: (600, 0) for ch in glyphs})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({'familyName': 'Agent Grid CC0', 'styleName': 'Regular', 'uniqueFontIdentifier': 'AgentGridCC0-v1',
        'fullName': 'Agent Grid CC0 Regular', 'psName': 'AgentGridCC0-Regular',
        'copyright': 'Original fixture glyph drawings dedicated to CC0-1.0'})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost(); fb.setupMaxp(); fb.font['head'].created = fb.font['head'].modified = 2082844800
    fb.font.recalcTimestamp = False; fb.save(str(path))

def run(output, work):
    import numpy as np
    from PIL import Image
    output.mkdir(parents=True, exist_ok=False); work.mkdir(parents=True, exist_ok=False)
    before = frozen(); old = work/'baseline'; calls = []
    archive = subprocess.check_output(['git', '-c', 'core.autocrlf=false', 'archive', '--format=zip', BASELINE,
        'product/src', 'docs/specs/agent-project.schema.json'], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for item in z.infolist():
            if item.is_dir():
                continue
            path = (old/item.filename).resolve(); assert path.is_relative_to(old.resolve())
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(z.read(item))
    baseline_hashes = {p.relative_to(old).as_posix(): sha(p) for p in old.rglob('*') if p.is_file()}
    bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    def cli(*args, baseline=False, expected=0):
        started = time.monotonic()
        result = subprocess.run([sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap,
            str(old/'product/src' if baseline else ROOT/'product/src'), *map(str, args)], cwd=ROOT,
            capture_output=True, timeout=300)
        index = len(calls)
        for name, raw in (('stdout', result.stdout), ('stderr', result.stderr)):
            (work/f'{index:03}.{name}.log').write_bytes(raw)
        value = json.loads(result.stdout.decode('utf-8-sig')) if result.stdout.strip() else {'stderr': result.stderr.decode('utf-8', 'replace')}
        calls.append({'index': index, 'args': list(map(str, args)), 'baseline': baseline,
            'exit_code': result.returncode, 'expected_exit_code': expected, 'seconds': time.monotonic()-started,
            'stdout_sha256': 'sha256:'+hashlib.sha256(result.stdout).hexdigest(),
            'stderr_sha256': 'sha256:'+hashlib.sha256(result.stderr).hexdigest()})
        save(work/'partial-calls.json', calls)
        assert result.returncode == expected, (args, value)
        return value
    def ff(args, data=None):
        return subprocess.run(['ffmpeg', '-v', 'error', '-y', '-threads', '1', *map(str, args)],
            input=data, check=True, capture_output=True, timeout=300).stdout
    def decode(path, audio=False, canvas=(W, H)):
        if audio:
            return np.frombuffer(ff(['-i', path, '-vn', '-ar', SR, '-ac', 2, '-f', 'f32le', 'pipe:1']), '<f4').reshape(-1, 2)
        return np.frombuffer(ff(['-i', path, '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1']), np.uint8).reshape(-1, canvas[1], canvas[0], 3)
    inputs = ROOT/'docs/assets/source-transitions-20261017'
    source_record = json.loads((inputs/'verification.json').read_text(encoding='utf-8'))
    for sid in 'abc':
        for name in (f'source-{sid}.mp4', f'sound-{sid}.wav'):
            assert sha(inputs/name) == source_record['files'][name]['sha256']
            shutil.copyfile(inputs/name, output/name)
    grid_font(output/'agent-grid-cc0.ttf')
    (output/'warm.cube').write_text('TITLE "Agent fixture warm"\nLUT_3D_SIZE 2\n'+''.join(
        f'{min(1, r*.9+.05)} {g*.95} {b*.9}\n' for b in range(2) for g in range(2) for r in range(2)), encoding='utf-8')
    (output/'captions.srt').write_text('1\n00:00:01,000 --> 00:00:03,000\nCTA\n\n2\n00:00:03,000 --> 00:00:05,000\nCTA\n', encoding='utf-8')
    provenance = {'license_spdx': 'CC0-1.0', 'source': 'V35 original procedural counters/moving blocks/stereo tones plus original grid glyphs, captions and LUT',
        'original_provenance': 'docs/assets/source-transitions-20261017/fixture-provenance.json',
        'original_provenance_sha256': sha(inputs/'fixture-provenance.json'), 'generator': 'scripts/smoke_fragments.py',
        'generator_sha256': sha(Path(__file__)), 'source_video': {'width': W, 'height': H, 'fps': FPS, 'frames': 80, 'seconds': 8},
        'source_audio': {'sample_rate': SR, 'channels': 2, 'sample_frames': 8*SR}, 'new_model_inference': 0,
        'browser_invocations': 0, 'font': 'original CC0 grid glyphs; FontTools only used by fixture generator',
        'baseline_ref': BASELINE}
    save(output/'fixture-provenance.json', provenance)
    source = work/'source'; cli('project', 'init', source)
    rights_args = ['--verification-status', 'verified', '--license-spdx', 'CC0-1.0', '--permitted-use', 'commercial_ad',
                   '--evidence', output/'fixture-provenance.json']
    for sid in 'abc':
        for kind, path in (('video', output/f'source-{sid}.mp4'), ('audio', output/f'sound-{sid}.wav')):
            cli('media', 'ingest', '--project', source, '--input', path, '--asset-id', kind+'_'+sid, *rights_args)
    for aid, path in (('font', output/'agent-grid-cc0.ttf'), ('captions', output/'captions.srt')):
        cli('media', 'ingest', '--project', source, '--input', path, '--asset-id', aid, *rights_args)
    cli('lut', 'register', '--project', source, '--input', output/'warm.cube', '--lut-id', 'warm', *rights_args)
    p = json.loads((source/'project.json').read_text(encoding='utf-8')); assets = {a['id']: a for a in p['assets']}
    p['settings']['canvas'].update(width=W, height=H); p['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
    def clip(cid, start, duration, **extra):
        return {'id': cid, 'timeline_start_tick': start, 'duration_tick': duration, 'source_in_tick': 2*TPS, 'source_out_tick': 2*TPS+duration, **extra}
    style = {'fontfile': assets['font']['uri'], 'font_asset_id': 'font', 'font_size': 18, 'font_color': '#ffffff', 'x': .08, 'y': .72}
    root = p['sequences'][0]; root.update(duration_tick=7*TPS, markers=[{'id': 'cta_marker', 'at_tick': TPS, 'label': 'CTA'}])
    root['tracks'][0]['clips'] = [clip('excluded', 0, TPS, asset_id='video_c'),
        clip('a', TPS, 2*TPS, asset_id='video_a', link_id='link_a', effects=[{'type': 'lut3d', 'parameters': {'lut_id': 'warm', 'intensity': .4}}]),
        clip('b', 3*TPS, 2*TPS, asset_id='video_b', link_id='link_b'),
        clip('nested', 5*TPS, 2*TPS, sequence_id='child', source_in_tick=0, source_out_tick=2*TPS)]
    root['tracks'][1]['audio'] = {'volume': .8, 'pan': -.1}
    root['tracks'][1]['clips'] = [clip(sid+'_sound', start*TPS, 2*TPS, asset_id='audio_'+sid, link_id='link_'+sid,
        audio={'volume': .7}) for sid, start in (('a', 1), ('b', 3))]
    root['tracks'].append({'id': 'subtitles', 'kind': 'subtitle', 'order': 2, 'clips': [
        clip('caption', TPS, 4*TPS, asset_id='captions', link_id='link_a', source_in_tick=0, source_out_tick=4*TPS,
             subtitle={'asset_uri': assets['captions']['uri'], 'style': copy.deepcopy(style)})]})
    child = {'id': 'child', 'name': 'CTA child', 'canvas': {'width': 120, 'height': 68}, 'duration_tick': 2*TPS,
        'tracks': [{'id': 'child_v', 'kind': 'video', 'order': 0, 'clips': [clip('child_picture', 0, 2*TPS, asset_id='video_c')]},
                   {'id': 'child_a', 'kind': 'audio', 'order': 1, 'audio': {'volume': .5},
                    'clips': [clip('child_sound', 0, 2*TPS, asset_id='audio_c')]}], 'markers': []}
    p['sequences'].append(child); save(source/'project.json', p)
    request = work/'transition.json'; save(request, {'action': 'add', 'id': 'ab', 'from_clip_id': 'a', 'to_clip_id': 'b', 'duration_tick': TPS})
    cli('timeline', 'transition', '--project', source, '--input', request)
    authored = json.loads((source/'project.json').read_text(encoding='utf-8'))
    source_ledger = json.loads((source/'rights-ledger.json').read_text(encoding='utf-8'))
    save(output/'authored-source.json', authored)
    library = output/'library'
    selections = {'whole': ['a', 'b', 'nested', 'caption'], 'partial': ['a'], 'child': ['nested']}
    for version, kind in enumerate(selections, 1):
        req = work/f'save-{kind}.json'; save(req, {'id': 'cta', 'version': version, 'name': 'CTA '+kind,
            'tags': ['advertising', kind], 'sequence_id': 'seq_main', 'clip_ids': selections[kind]})
        dry = cli('fragment', 'save', '--project', source, '--library', library, '--input', req, '--dry-run')
        result = cli('fragment', 'save', '--project', source, '--library', library, '--input', req,
            '--expected-project-sha256', dry['data']['plan']['project_sha256'], '--expected-fragment-sha256', dry['data']['plan']['fragment_sha256'])
        save(output/f'library-{kind}-plan.json', result)
    cli('fragment', 'list', '--library', library, '--query', 'advertising')
    for version in (1, 2, 3):
        cli('fragment', 'inspect', '--library', library, '--id', 'cta', '--version', version)
    lib_before = {p.relative_to(library).as_posix(): sha(p) for p in library.rglob('*') if p.is_file()}
    # Independent source selection sets, stated directly rather than consuming
    # the fragment payload's selected or remapped sequence graph.
    included = {'whole': {'a', 'b', 'nested', 'caption', 'a_sound', 'b_sound'},
                'partial': {'a', 'b', 'caption', 'a_sound', 'b_sound'}, 'child': {'nested'}}
    entry_ranges = {'whole': (TPS, 7*TPS), 'partial': (TPS, 5*TPS), 'child': (5*TPS, 7*TPS)}
    def target(name, canvas=(W, H)):
        target = work/name; cli('project', 'init', target)
        cli('media', 'ingest', '--project', target, '--input', output/'source-c.mp4', '--asset-id', 'video_a', *rights_args)
        project = json.loads((target/'project.json').read_text(encoding='utf-8'))
        project['settings'] = copy.deepcopy(authored['settings']); project['settings']['canvas'].update(width=canvas[0], height=canvas[1])
        project['sequences'][0]['duration_tick'] = TPS
        project['sequences'][0]['tracks'][0]['clips'] = [clip('target_intro', 0, TPS, asset_id='video_a', source_in_tick=0, source_out_tick=TPS)]
        save(target/'project.json', project)
        return target
    def render(project, name, *, baseline=False, selected=None, canvas=(W, H), publish=True):
        path = project/'renders'/(name+'.mkv')
        args = ['render', '--project', project, '--output', path, '--container', 'mkv', '--crf', 0,
                '--pixel-format', 'yuv444p', '--audio-codec', 'pcm_f32le']
        if selected:
            args += ['--sequence-id', selected]
        if publish:
            args += ['--publish']
        response = cli(*args, baseline=baseline)
        shutil.copyfile(path, output/(name+'.mkv'))
        ff(['-i', path, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', output/(name+'.mp4')])
        save(output/(name+'-render.json'), response)
        return decode(path, canvas=canvas), decode(path, audio=True)
    def reference(case_id, kind, repeats, canvas, edited=False):
        path = work/(case_id+'-reference'); shutil.copytree(source, path)
        pp = copy.deepcopy(authored); seq = pp['sequences'][0]
        seq['canvas'] = {'width': W, 'height': H}
        for t in seq['tracks']:
            t['clips'] = [c for c in t['clips'] if c['id'] in included[kind]]
        if kind == 'child':
            seq['source_transitions'] = []
        if edited:
            cap = next(c for t in seq['tracks'] for c in t['clips'] if c['id'] == 'caption')
            cap['subtitle'].pop('asset_uri'); cap['subtitle']['text'] = 'EDIT'
        pp['settings']['canvas'].update(width=canvas[0], height=canvas[1])
        # Source-child authored canvas remains the original 120x68.
        a, b = entry_ranges[kind]; dur = b-a
        wrappers = [clip('ref_'+str(i), TPS+i*dur, dur, sequence_id='seq_main', source_in_tick=a, source_out_tick=b) for i in range(repeats)]
        intro = clip('ref_intro', 0, TPS, asset_id='video_c', source_in_tick=0, source_out_tick=TPS)
        pp['sequences'].insert(0, {'id': 'reference', 'name': 'manual isolated source reference', 'duration_tick': TPS+dur*repeats,
            'tracks': [{'id': 'reference_track', 'kind': 'video', 'order': 0, 'clips': [intro, *wrappers]}]})
        save(path/'project.json', pp)
        return render(path, case_id+'-reference', baseline=True, selected='reference', canvas=canvas)
    cases = []
    for cid, kind, repeats, canvas, edited in [('C01', 'whole', 1, (W, H), False), ('C02', 'partial', 1, (W, H), False),
            ('C03', 'child', 1, (W, H), False), ('C04', 'partial', 2, (W, H), False),
            ('C05', 'partial', 1, (H, W), False), ('C06', 'partial', 1, (W, H), True)]:
        dst = target(cid, canvas); a, b = entry_ranges[kind]; version = list(selections).index(kind)+1
        plans = []
        for index in range(repeats):
            req = work/(cid+f'-apply-{index}.json'); save(req, {'id': 'cta', 'version': version, 'sequence_id': 'seq_main',
                'track_id': 'track_video_1', 'at_tick': TPS+index*(b-a), 'instance_id': cid+'_'+str(index)})
            dry = cli('fragment', 'apply', '--project', dst, '--library', library, '--input', req, '--dry-run')
            applied = cli('fragment', 'apply', '--project', dst, '--library', library, '--input', req,
                '--expected-project-sha256', dry['data']['plan']['project_sha256'], '--expected-fragment-sha256', dry['data']['plan']['fragment_sha256'])
            plans.append(applied['data']['plan'])
        if edited:
            pp = json.loads((dst/'project.json').read_text(encoding='utf-8'))
            caption_id = plans[0]['id_maps']['clip']['caption']
            cap = next(c for s in pp['sequences'] for t in s['tracks'] for c in t['clips'] if c['id'] == caption_id)
            cap['subtitle'].pop('asset_uri'); cap['subtitle']['text'] = 'EDIT'
            save(dst/'project.json', pp)
        cli('validate', '--project', dst, '--strict-rights'); cli('policy', 'audit', '--project', dst)
        actual, audio = render(dst, cid+'-actual', canvas=canvas)
        expected, sound = reference(cid, kind, repeats, canvas, edited)
        assert actual.shape == expected.shape and np.array_equal(actual, expected), (cid, actual.shape, expected.shape)
        assert audio.shape == sound.shape and np.max(np.abs(audio-sound)) <= 1e-8, cid
        data = {'id': cid, 'kind': kind, 'repeat_count': repeats, 'edited_imported_caption': edited,
            'canvas': list(canvas), 'frames': len(actual), 'sample_frames': len(audio),
            'rgb_exact_fixed_V36_manual_reference': True, 'pcm_max_abs_error': float(np.max(np.abs(audio-sound))),
            'rgb_sha256': 'sha256:'+hashlib.sha256(actual.tobytes()).hexdigest(),
            'pcm_sha256': 'sha256:'+hashlib.sha256(audio.tobytes()).hexdigest(), 'plans': plans,
            'original_asset_same_id_different_content_preserved': True}
        cases.append(data); save(output/(cid+'-verification.json'), data)
    assert lib_before == {p.relative_to(library).as_posix(): sha(p) for p in library.rglob('*') if p.is_file()}
    # Expected failures use separate projects/copies, leaving published library
    # versions and all positive author graphs intact.
    negative = []
    req = work/'negative.json'; save(req, {'id': 'cta', 'version': 2, 'sequence_id': 'seq_main', 'track_id': 'track_video_1', 'at_tick': TPS})
    bad = work/'damaged-library'; shutil.copytree(library, bad)
    manifest = next(p for p in bad.glob('entries/*/2/fragment.json'))
    payload = json.loads(manifest.read_text(encoding='utf-8'))
    damaged = manifest.parent/payload['project']['assets'][0]['uri']; damaged.write_bytes(damaged.read_bytes()+b'tampered')
    dst = target('N01')
    for cid, lib, flags, expected_code in [('N01', bad, [], 'FRAGMENT_RESOURCE_HASH_MISMATCH'),
            ('N02', library, ['--expected-project-sha256', 'sha256:'+'0'*64], 'FRAGMENT_PROJECT_CHANGED')]:
        result = cli('fragment', 'apply', '--project', dst, '--library', lib, '--input', req, *flags, expected=2)
        assert result['errors'][0]['code'] == expected_code
        negative.append({'id': cid, 'error_code': expected_code, 'response': result})
    pp = json.loads((dst/'project.json').read_text(encoding='utf-8')); pp['settings']['timebase']['display_fps']['num'] = 20; save(dst/'project.json', pp)
    result = cli('fragment', 'apply', '--project', dst, '--library', library, '--input', req, expected=2)
    assert result['errors'][0]['code'] == 'FRAGMENT_CONTEXT_MISMATCH'; negative.append({'id': 'N03', 'response': result})
    dst = target('N04'); collision = json.loads(req.read_text(encoding='utf-8')); collision['at_tick'] = 0; save(req, collision)
    result = cli('fragment', 'apply', '--project', dst, '--library', library, '--input', req, expected=2)
    assert result['errors'][0]['code'] == 'FRAGMENT_TARGET_COLLISION'; negative.append({'id': 'N04', 'response': result})
    restricted = work/'restricted-source'; shutil.copytree(source, restricted)
    ledger = copy.deepcopy(source_ledger)
    record = next(r for r in ledger['records'] if r['asset_id'] == 'video_a' and r.get('active', True))
    record.update(verification_status='blocked', restrictions=['fixture-review-required'])
    save(restricted/'rights-ledger.json', ledger)
    req_save = work/'restricted-save.json'; save(req_save, {'id': 'restricted', 'version': 1, 'sequence_id': 'seq_main', 'clip_ids': ['a']})
    restricted_library = work/'restricted-library'
    cli('fragment', 'save', '--project', restricted, '--library', restricted_library, '--input', req_save)
    dst = target('N05'); save(req, {**collision, 'id': 'restricted', 'version': 1, 'at_tick': TPS})
    cli('fragment', 'apply', '--project', dst, '--library', restricted_library, '--input', req)
    result = cli('render', '--project', dst, '--output', dst/'renders/blocked.mkv', '--publish', expected=7)
    assert result['errors'][0]['code'] == 'PROJECT_INVALID'
    rejected_validation = json.loads(result['errors'][0]['cause'])
    assert 'RIGHTS_STATUS_BLOCKED' in {e['code'] for e in rejected_validation['errors']}
    assert not (dst/'renders/blocked.mkv').exists(); negative.append({'id': 'N05', 'response': result, 'no_encoded_output': True})
    save(output/'expected-rejections.json', negative)
    # Two paired rows: fixed manual reference / actual library application.
    panels = []
    for cid in ('C01', 'C02'):
        a = decode(output/(cid+'-reference.mkv'))[:40]; b = decode(output/(cid+'-actual.mkv'))[:40]
        panels.append(np.concatenate((a, b), axis=2))
    comparison = np.concatenate(panels, axis=1)
    ff(['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{2*W}x{2*H}', '-r', FPS, '-i', 'pipe:0',
        '-an', '-c:v', 'libx264rgb', '-preset', 'ultrafast', '-crf', 0, output/'comparison.mp4'], comparison.tobytes())
    gif_frames = [Image.fromarray(frame) for frame in comparison[::2]]
    gif_frames[0].save(output/'comparison.gif', save_all=True, append_images=gif_frames[1:], duration=200,
                       loop=0, optimize=False, disposal=2)
    after = frozen(); assert before == after
    assert baseline_hashes == {p.relative_to(old).as_posix(): sha(p) for p in old.rglob('*') if p.is_file()}
    with zipfile.ZipFile(output/'cli-logs.zip', 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(work.glob('*.log')):
            z.write(path, path.name)
        z.writestr('calls.json', json.dumps(calls, ensure_ascii=False, indent=2)+'\n')
    record = {'status': 'passed', 'case_count': len(cases), 'expected_rejections': len(negative), 'cases': cases,
        'cli_count': len(calls), 'cli_success': sum(c['exit_code'] == 0 for c in calls), 'calls': calls,
        'new_output_frames': sum(c['frames'] for c in cases), 'new_output_sample_frames': sum(c['sample_frames'] for c in cases),
        'frozen_before': before, 'frozen_after': after, 'frozen_equal': True, 'baseline_ref': BASELINE,
        'baseline_file_hashes': baseline_hashes, 'library_after_insertions_unchanged': True,
        'new_model_inference': 0, 'browser_invocations': 0,
        'limits': ['controlled_procedural_fixtures_not_natural_advertising', 'fixed_manual_author_graph_reference_uses_existing_renderer',
                   'no_continuous_playback_or_listening', 'no_full_capcut_parity'],
        'files': {p.relative_to(output).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()}}
    save(output/'verification.json', record)
    print(json.dumps({k: record[k] for k in ('case_count', 'expected_rejections', 'cli_count', 'cli_success', 'new_output_frames', 'new_output_sample_frames')}, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True); parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args(); run(args.output.resolve(), args.work.resolve())
