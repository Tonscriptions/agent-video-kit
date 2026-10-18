"""Real local color animation, original patterns, static native oracles and packages."""
from __future__ import annotations
import argparse
import contextlib
import copy
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import wave
import zipfile

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASE = '2f6ee73c37ba05c33fe89495d19b6b4c3d2a612f'
TPS, SR, W, H = 90000, 48000, 160, 96


def digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path): return digest(path.read_bytes())
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def effect(kind, channels, duration=2*TPS, parameters=None):
    tracks = []
    for prop, (left, right) in channels.items():
        tracks.append({'property': prop, 'keyframes': [
            {'at_tick': 0, 'value': left, 'interpolation': 'linear'},
            {'at_tick': duration, 'value': right, 'interpolation': 'linear'}]})
    return {'type': kind, 'parameters': parameters or {}, 'keyframes': tracks}


def run(work, public):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    work.mkdir(parents=True, exist_ok=False); public.mkdir(parents=True, exist_ok=False)
    (public/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    os.environ['AI_AD_EDITOR_RUNTIME_DIR'] = str(work/'runtime')
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.path.insert(0, str(ROOT/'product/src'))
    from ai_ad_editor.cli import main
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.project import save_project
    configure_local_runtime(); before = frozen(); calls = []; natives = []; cases = []; refs = {}
    started = time.monotonic()

    def cli(*args, expected=0):
        out = io.StringIO()
        with contextlib.redirect_stdout(out): code = main(list(map(str, args)))
        value = json.loads(out.getvalue()); path = public/f'cli/{len(calls)+1:03}.json'; save(path, value)
        calls.append({'arguments': list(map(str, args)), 'exit_code': code, 'expected_exit_code': expected,
                      'result': path.relative_to(public).as_posix(), 'result_sha256': sha(path)})
        save(public/'calls.json', calls)
        assert code == expected, (args, value)
        return value

    def native(*args, data=None, cwd=None):
        command = ['ffmpeg', '-hide_banner', '-v', 'error', '-y', *map(str, args)]
        done = subprocess.run(command, input=data, capture_output=True, timeout=180, cwd=cwd)
        natives.append({'command': command, 'input_sha256': digest(data) if data is not None else None,
                        'exit_code': done.returncode, 'stdout_sha256': digest(done.stdout),
                        'stderr_sha256': digest(done.stderr)})
        save(public/'native-calls.json', natives)
        assert done.returncode == 0, done.stderr.decode('utf-8', 'replace')
        return done.stdout

    def decode(path, alpha=False):
        prefix = ['-c:v', 'libvpx-vp9'] if alpha else []
        raw = native(*prefix, '-i', path, '-map', '0:v:0', '-an', '-fps_mode', 'passthrough',
                     '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1')
        return np.frombuffer(raw, dtype='u1').reshape(-1, H, W, 4)

    def pcm(path):
        raw = native('-i', path, '-map', '0:a:0', '-vn', '-ar', SR, '-ac', 2, '-f', 'f32le', 'pipe:1')
        return np.frombuffer(raw, dtype='<f4').reshape(-1, 2)

    def cl(cid='color_clip', duration=2*TPS, at=0, **fields):
        return {'id': cid, 'asset_id': 'frames', 'timeline_start_tick': at, 'duration_tick': duration,
                'source_in_tick': 0, 'source_out_tick': duration, **fields}

    def tr(tid, kind, clips, order=0): return {'id': tid, 'kind': kind, 'order': order, 'clips': clips}

    def author(path, p):
        save_project(path, p); cli('validate', '--project', path, '--strict-rights')

    def encode(path, name, alpha=False):
        target = path/'renders'/(name+('.webm' if alpha else '.mkv'))
        args = ['render', '--project', path, '--output', target, '--container', 'webm' if alpha else 'mkv',
                '--video-codec', 'libvpx-vp9' if alpha else 'libx264', '--crf', '0',
                '--pixel-format', 'yuva420p' if alpha else 'yuv444p',
                '--audio-codec', 'libopus' if alpha else 'pcm_f32le', '--publish']
        result = cli(*args)
        shutil.copyfile(target, public/target.name)
        shutil.copyfile(result['data']['manifest'], public/(name+'.manifest.json'))
        return target, decode(target, alpha), pcm(target), result

    def static(source, chain, *, raw=False, after_composite=False):
        key = digest(source.tobytes())+' '+chain+' '+str((raw, after_composite))
        if key not in refs:
            args = ['-filter_threads', '1', '-filter_complex_threads', '1', '-f', 'rawvideo',
                    '-pix_fmt', 'rgba', '-s', f'{W}x{H}', '-r', '10', '-i', 'pipe:0']
            if raw:
                pixels = native(*args, '-vf', chain, '-frames:v', 1,
                    '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1', data=source.tobytes())
            else:
                # Pin the same compositing and declared 709 delivery boundary.
                # Direct float->RGBA reference prematurely clips/quantizes exposure.
                graph = ('[0:v]null[fg];' if after_composite else '[0:v]'+chain+'[fg];')
                graph += f'color=c=black:s={W}x{H}:r=10:d=0.1[bg];[bg][fg]overlay=format=auto'
                if after_composite: graph += ','+chain
                graph += '[v]'
                encoded = native(*args, '-filter_complex', graph, '-map', '[v]', '-frames:v', 1,
                    '-c:v', 'libx264', '-crf', 0, '-pix_fmt', 'yuv444p', '-color_primaries', 'bt709',
                    '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv', '-f', 'matroska',
                    'pipe:1', data=source.tobytes())
                pixels = native('-i', 'pipe:0', '-an', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1', data=encoded)
            refs[key] = np.frombuffer(pixels, dtype='u1').reshape(H, W, 4)
        return refs[key]

    def oracle(chain, count=20, rate=Fraction(10)):
        return np.stack([static(source, chain(float(Fraction(i, 1)/rate))) for i in range(count)])

    def record(path, name, expected, duration, scope, rate=Fraction(10), alpha=False, alpha_reference=None):
        target, actual, audio, result = encode(path, name, alpha)
        assert len(actual) == math.ceil(Fraction(duration, TPS)*rate), (name, len(actual))
        assert actual.shape == expected.shape, (name, actual.shape, expected.shape)
        rgb = int(np.abs(actual[..., :3].astype('i2')-expected[..., :3].astype('i2')).max())
        alpha_error = int(np.abs(actual[..., 3].astype('i2')-expected[..., 3].astype('i2')).max())
        if alpha:
            assert alpha_error == 0, (name, 'alpha', alpha_error)
            expected_audio = alpha_reference
        else:
            assert rgb <= 2, (name, 'RGB', rgb)
            assert alpha_error == 0
            expected_audio = signal[:math.ceil(Fraction(duration*SR, TPS))]
        assert audio.shape == expected_audio.shape, (name, audio.shape, expected_audio.shape)
        pcm_error = float(np.abs(audio-expected_audio).max())
        assert pcm_error <= 2e-6, (name, 'PCM', pcm_error)
        native('-i', target, '-c:v', 'libx264', '-crf', 16, '-pix_fmt', 'yuv420p', '-c:a', 'aac', public/(name+'.mp4'))
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(target)],
                               capture_output=True, check=True, timeout=60)
        (public/(name+'-probe.json')).write_bytes(probe.stdout)
        expected_path = public/(name+'-reference.npz')
        np.savez_compressed(expected_path, rgba=expected)
        cli('policy', 'audit', '--project', path)
        cli('convert', 'export', '--project', path, '--target-format', 'package', '--output', public/(name+'.aevpkg.zip'))
        manifest = json.loads((public/(name+'.manifest.json')).read_bytes())
        def items(rows):
            for row in rows:
                yield row
                if isinstance(row.get('inputs'), list): yield from items(row['inputs'])
        runtime = [x for x in items(manifest['inputs']) if x.get('kind') == 'effect-automation']
        assert runtime, name
        for ordinal, row in enumerate(runtime):
            command = path/row['command_file']; assert sha(command) == row['command_file_sha256']
            shutil.copyfile(command, public/f'{name}-commands-{ordinal:02}.ffcmd')
        row = {'name': name, 'scope': scope, 'frames': len(actual), 'stereo_sample_frames': len(audio),
               'fps': str(rate), 'duration_tick': duration, 'max_rgb_error': rgb,
               'rgb_acceptance_applies': not alpha, 'max_alpha_error': alpha_error,
               'max_pcm_error': pcm_error, 'runtime_instances': len(runtime),
               'command_count': sum(x['command_count'] for x in runtime),
               'decoded_rgba_sha256': digest(actual.tobytes()), 'decoded_pcm_sha256': digest(audio.tobytes()),
               'reference_sha256': sha(expected_path), 'output': target.name, 'output_sha256': sha(public/target.name)}
        cases.append(row); save(public/'cases.json', cases)
        return actual

    try:
        image = Image.new('RGBA', (W, H), (42, 50, 68, 255)); draw = ImageDraw.Draw(image)
        for x in range(W):
            draw.line((x, 0, x, H-1), fill=(20+int(210*x/W), 30+int(165*x/W), 80+int(120*x/W), 255))
        for x, color in zip((6, 40, 74, 108), ((35, 35, 35), (90, 90, 90), (160, 160, 160), (225, 225, 225))):
            draw.rectangle((x, 7, x+25, 28), fill=(*color, 255))
        draw.rounded_rectangle((60, 38, 100, 91), radius=8, fill=(105, 152, 180, 255), outline=(230, 222, 196, 255), width=2)
        draw.rectangle((71, 32, 89, 39), fill=(210, 202, 174, 255))
        draw.rectangle((65, 54, 95, 70), fill=(230, 222, 196, 255))
        image.save(public/'source.png'); source = np.asarray(image)
        native('-loop', '1', '-i', public/'source.png', '-t', '4', '-r', '10', '-an',
               '-c:v', 'ffv1', '-pix_fmt', 'bgra', public/'source.mkv')
        n = np.arange(4*SR, dtype=np.float64)
        raw = np.stack((np.rint(4500*np.sin(2*np.pi*(170*n/SR+38*(n/SR)**2))),
                        np.rint(3900*np.cos(2*np.pi*(230*n/SR+17*(n/SR)**2)))), axis=1).astype('<i2')
        with wave.open(str(public/'source.wav'), 'wb') as stream:
            stream.setnchannels(2); stream.setsampwidth(2); stream.setframerate(SR); stream.writeframes(raw.tobytes())
        signal = raw.astype(np.float32)/32768
        for name in ('DejaVuSans.ttf', 'LICENSE_DEJAVU'):
            shutil.copyfile(ROOT/'docs/assets/retime-release-20261019-v57'/name, public/name)
        save(public/'source-provenance.json', {'procedural_picture_video_audio_license': 'CC0-1.0',
             'source_image': sha(public/'source.png'), 'source_video': sha(public/'source.mkv'),
             'source_audio': sha(public/'source.wav'), 'font_license': 'Bitstream-Vera',
             'font_notice': 'LICENSE_DEJAVU', 'font_sha256': sha(public/'DejaVuSans.ttf'),
             'source_frames': 40, 'fps': '10/1', 'width': W, 'height': H,
             'stereo_sample_frames': 4*SR, 'sample_rate': SR,
             'purpose': 'original controlled color patches; not a natural commercial quality corpus'})
        native('-i', public/'source.mkv', '-i', public/'source.wav', '-c:v', 'libx264', '-crf', 16,
               '-pix_fmt', 'yuv420p', '-c:a', 'aac', public/'source-preview.mp4')
        base = work/'base'; cli('project', 'init', base)
        for filename, aid, license in (('source.mkv', 'frames', 'CC0-1.0'), ('source.png', 'picture', 'CC0-1.0'),
                                      ('source.wav', 'sound', 'CC0-1.0'), ('DejaVuSans.ttf', 'font', 'Bitstream-Vera')):
            cli('media', 'ingest', '--project', base, '--input', public/filename, '--asset-id', aid,
                '--verification-status', 'verified', '--permitted-use', 'commercial_ad', '--license-spdx', license,
                '--source', 'original procedural fixture or unmodified licensed font',
                '--creator', 'fixture authors or DejaVu/Bitstream authors',
                '--evidence', public/('LICENSE_DEJAVU' if aid == 'font' else 'source-provenance.json'))
        p = json.loads((base/'project.json').read_bytes()); sid = p['sequences'][0]['id']
        p['settings']['canvas'].update(width=W, height=H)
        p['settings']['timebase']['display_fps'] = {'num': 10, 'den': 1}
        p['sequences'] = [{'id': sid, 'name': 'actual native color parameters', 'duration_tick': 2*TPS,
            'tracks': [tr('shots', 'video', [cl()]), tr('audio', 'audio', [cl('music', asset_id='sound')])]}]
        author(base, p)

        def make(name, value=None, duration=2*TPS, rate=Fraction(10)):
            path = work/name; shutil.copytree(base, path); q = copy.deepcopy(p)
            q['settings']['timebase']['display_fps'] = {'num': rate.numerator, 'den': rate.denominator}
            s = q['sequences'][0]; s['duration_tick'] = duration
            s['tracks'][0]['clips'] = [cl(duration=duration, effects=[value] if value else [])]
            s['tracks'][1]['clips'] = [cl('music', asset_id='sound', duration=duration)]
            return path, q, s

        temperature = lambda t: 'colorbalance=rs={:.6f}:gs={:.6f}:bs={:.6f}'.format(
            -.3*max(-1, min(1, (3000+4500*t-6500)/6500)),
            -.05*max(-1, min(1, (3000+4500*t-6500)/6500)),
            .3*max(-1, min(1, (3000+4500*t-6500)/6500)))
        balance = lambda t: f'colorbalance=rs={-.25+.25*t:.6f}:gs={.15-.15*t:.6f}:bs={-.1+.15*t:.6f}'
        wheel_channels = {f'{tone}_{channel}': (-.03*(1+i*3+j), .03*(1+i*3+j))
            for i, tone in enumerate(('shadows', 'midtones', 'highlights')) for j, channel in enumerate(('red', 'green', 'blue'))}
        wheel_options = [(channel+tone, .03*(1+i*3+j)) for i, tone in enumerate('smh') for j, channel in enumerate('rgb')]
        wheel = lambda t: 'colorbalance='+':'.join(f'{name}={-a+a*t:.6f}' for name, a in wheel_options)+':pl=1'
        exposure = lambda t: f'exposure=exposure={-.5+.6*t:.6f}:black={.03-.02*t:.6f}'
        levels = lambda t: 'colorlevels='+':'.join(
            f'{c}{option}={left+(right-left)*t/2:.6f}' for option, left, right in
            (('imin', 0, .08), ('imax', 1, .9), ('omin', 0, .05), ('omax', .7, 1)) for c in 'rgb')
        definitions = [
            ('CA01', effect('color_temperature', {'kelvin': (3000, 12000)}), temperature),
            ('CA02', effect('color_balance', {'red': (-.25, .25), 'green': (.15, -.15), 'blue': (-.1, .2)}), balance),
            ('CA03', effect('color_wheel', wheel_channels, parameters={'preserve_luma': True}), wheel),
            ('CA04', effect('exposure', {'amount': (-.5, .7), 'black': (.03, -.01)}), exposure),
            ('CA05', effect('color_levels', {'input_black': (0, .08), 'input_white': (1, .9),
                                          'output_black': (0, .05), 'output_white': (.7, 1)}), levels),
        ]
        expected_rows = {}; author_rows = {}; projects = {}
        for name, value, chain in definitions:
            path, q, _ = make(name, value); author(path, q)
            expected_rows[name] = oracle(chain)
            author_rows[name] = np.stack([static(source, chain(i/10), raw=True) for i in range(20)])
            record(path, name, expected_rows[name], 2*TPS,
                   'independent static native FFmpeg numeric parameters with the same opaque composite and declared 709 encoding boundary')
            projects[name] = path

        path, q, s = make('CA06')
        child = {'id': 'child', 'name': 'repeated independent target scope', 'duration_tick': TPS,
                 'tracks': [tr('child_shots', 'video', [cl('inner', duration=TPS, effects=[
                     effect('color_balance', {'red': (0, .4)}, TPS),
                     effect('color_balance', {'blue': (.2, -.2)}, TPS)])])]}
        one = cl('one', duration=TPS, sequence_id='child'); one.pop('asset_id')
        two = copy.deepcopy(one); two.update(id='two', timeline_start_tick=TPS)
        s['tracks'][0]['clips'] = [one, two]; q['sequences'].append(child); author(path, q)
        repeated = oracle(lambda t: f'colorbalance=rs={.4*t:.6f},colorbalance=bs={.2-.4*t:.6f}', count=10)
        record(path, 'CA06', np.concatenate((repeated, repeated)), 2*TPS,
               'two repeated child instances, each with two same-backend command targets')

        path, q, s = make('CA07', duration=135000)
        child = {'id': 'curved_child', 'name': 'author clock', 'duration_tick': 2*TPS,
                 'tracks': [tr('child_shots', 'video', [cl('inner', effects=[effect('color_balance', {'blue': (-.3, .3)})])])]}
        container = cl('curved', duration=135000, source_out_tick=2*TPS, sequence_id=child['id'], reverse=True,
            speed_curve={'keyframes': [{'at_tick': 0, 'speed': 1., 'interpolation': 'hold'},
                                      {'at_tick': TPS, 'speed': 2., 'interpolation': 'hold'},
                                      {'at_tick': 2*TPS, 'speed': 2., 'interpolation': 'hold'}]})
        container.pop('asset_id'); s['tracks'][0]['clips'] = [container]; q['sequences'].append(child); author(path, q)
        def curved(t):
            elapsed = 1.5-t; author_time = elapsed if elapsed <= 1 else 1+2*(elapsed-1)
            return f'colorbalance=bs={-.3+.3*author_time:.6f}'
        record(path, 'CA07', oracle(curved, 15), 135000, 'independent inverse hold-curve and reverse author-clock reference')

        path, q, s = make('CA08', definitions[1][1], duration=108000)
        c = s['tracks'][0]['clips'][0]; c['source_out_tick'] = 2*TPS
        c['presentation_window'] = {'version': 1, 'authored_start_tick': 0,
                                    'authored_duration_tick': 2*TPS, 'offset_tick': 36000}
        author(path, q)
        expected_window = np.stack([static(frame, 'null') for frame in author_rows['CA02'][4:16]])
        record(path, 'CA08', expected_window, 108000,
                                'independent original parameter frames 4..15 after complete author window')

        path, q, s = make('CA09', duration=216000)
        child = {'id': 'frozen_child', 'name': 'complete nine-wheel picture', 'duration_tick': 2*TPS,
                 'tracks': [tr('child_shots', 'video', [cl('inner', effects=[definitions[2][1]])])]}
        container = cl('frozen', duration=216000, source_out_tick=2*TPS, sequence_id=child['id'],
                       freeze={'at_tick': 45000, 'duration_tick': 36000, 'audio_mode': 'silence'})
        container.pop('asset_id'); s['tracks'][0]['clips'] = [container]; q['sequences'].append(child); author(path, q)
        held_author = np.concatenate((author_rows['CA03'][:5], np.repeat(author_rows['CA03'][4:5], 4, axis=0), author_rows['CA03'][5:]))
        held = np.stack([static(frame, 'null') for frame in held_author])
        record(path, 'CA09', held, 216000, 'complete authored animated child followed by explicit four-frame compound hold')

        path, q, s = make('CA10')
        value = effect('color_temperature', {'kelvin': (3000, 12000)}, 108000)
        q['settings']['adjustments'] = [{'id': 'interval', 'start_tick': 31500, 'duration_tick': 108000, 'effects': [value]}]
        author(path, q)
        expected = np.repeat(static(source, 'null')[None], 20, axis=0).copy()
        for frame in range(4, 16):
            expected[frame] = static(source, temperature((frame-4)/10*2/1.2), after_composite=True)
        record(path, 'CA10', expected, 2*TPS, 'interval 0.35..1.55; actual first retained CFR sample resets local parameter clock')

        rate = Fraction(30000, 1001); duration = 90090
        path, q, s = make('CA11', effect('color_balance', {'red': (-.2, .2)}, duration), duration, rate)
        s['tracks'][0]['clips'][0]['asset_id'] = 'picture'; author(path, q)
        record(path, 'CA11', oracle(lambda t: f'colorbalance=rs={-.2+.4*t/1.001:.6f}', 30, rate), duration,
               'independent 30000/1001 display samples; exact 1.001-second authored duration', rate)

        path, q, s = make('CA12', duration=TPS)
        text = {'id': 'text', 'generator': {'type': 'text'}, 'timeline_start_tick': 0, 'duration_tick': TPS,
                'source_in_tick': 0, 'source_out_tick': TPS,
                'subtitle': {'text': 'TONE', 'style': {'font_asset_id': 'font', 'fontsize': 38,
                    'x': '12', 'y': '24', 'box': False, 'fontcolor': 'white@0.7'}},
                'transform': {'opacity': .75}}
        s['tracks'][0] = tr('text', 'subtitle', [text])
        q['settings']['output'] = {'container': 'webm', 'video': {'codec': 'libvpx-vp9', 'crf': 0, 'pixel_format': 'yuva420p'},
                                   'audio': {'codec': 'libopus', 'bitrate': '192k'}}
        author(path, q)
        _, control, control_audio, _ = encode(path, 'CA12-alpha-control', True)
        text['effects'] = [effect('color_balance', {'red': (-.8, .8)}, TPS)]
        author(path, q); record(path, 'CA12', control, TPS,
            'same-renderer glyph baseline: exact encoded alpha and unchanged encoded audio; RGB is not an accepted independent oracle',
            alpha=True, alpha_reference=control_audio)

        path, q, s = make('CA13', duration=93150)
        s['tracks'][0]['clips'] = [cl(duration=TPS, at=3150,
            effects=[effect('color_balance', {'red': (-.2, .2)}, TPS)])]
        author(path, q)
        expected = np.zeros((11, H, W, 4), dtype='u1'); expected[..., 3] = 255
        for frame in range(1, 11):
            expected[frame] = static(source, f'colorbalance=rs={-.2+.4*(frame/10-.035):.6f}')
        record(path, 'CA13', expected, 93150, 'direct clip begins at 35 ms; visible global CFR samples retain original local offset')

        path, q, s = make('CA14')
        value = {'type': 'color_balance', 'keyframes': [{'property': 'red', 'keyframes': [
            {'at_tick': 0, 'value': -.2, 'interpolation': 'hold'},
            {'at_tick': 45000, 'value': .4, 'interpolation': 'bezier', 'control_points': [1/3, 0, 2/3, 1]},
            {'at_tick': 135000, 'value': -.3, 'interpolation': 'ease_out'},
            {'at_tick': 180000, 'value': .3, 'interpolation': 'linear'}]}]}
        s['tracks'][0]['clips'][0]['effects'] = [value]; author(path, q)
        def mixed_curve(t):
            if t < .5: v = -.2
            elif t < 1.5:
                p = t-.5; v = .4-.7*(3*p*p-2*p*p*p)
            else:
                p = (t-1.5)/.5; v = -.3+.6*(1-(1-p)**2)
            return f'colorbalance=rs={v:.6f}'
        record(path, 'CA14', oracle(mixed_curve), 2*TPS, 'independent analytic hold, symmetric cubic Bezier and ease-out parameter segments')

        # Preserve actual old behavior from the published fixed V57 source.
        archive = work/'baseline-v57.zip'
        subprocess.run(['git', 'archive', '--format=zip', '--output', str(archive), BASE, '--', 'product/src'], cwd=ROOT, check=True)
        old = work/'baseline-v57'; old.mkdir()
        with zipfile.ZipFile(archive) as z: z.extractall(old)
        baseline_rows = []
        bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;sys.exit(main(sys.argv[1:]))'
        for name, _, _ in definitions:
            project = work/(name+'-v57'); shutil.copytree(projects[name], project)
            target = project/'renders'/(name+'-v57.mkv')
            cmd = [sys.executable, '-B', '-X', 'utf8', '-c', bootstrap, str(old/'product/src'),
                   'render', '--project', str(project), '--output', str(target), '--container', 'mkv',
                   '--video-codec', 'libx264', '--crf', '0', '--pixel-format', 'yuv444p', '--audio-codec', 'pcm_f32le', '--publish']
            done = subprocess.run(cmd, cwd=work, capture_output=True, timeout=180)
            (public/(name+'-v57.stdout.json')).write_bytes(done.stdout)
            (public/(name+'-v57.stderr.log')).write_bytes(done.stderr)
            assert done.returncode == 0, (name, done.stdout, done.stderr)
            shutil.copyfile(target, public/target.name); value = decode(target)
            maximum = int(np.abs(value[..., :3].astype('i2')-expected_rows[name][..., :3].astype('i2')).max())
            assert maximum > 2, (name, 'old implementation unexpectedly matches')
            baseline_rows.append({'name': name, 'command': cmd, 'exit_code': done.returncode,
                'reference_error': maximum, 'accepted': False, 'output_sha256': sha(public/target.name)})
        save(public/'baseline-v57.json', {'commit': BASE, 'archive_sha256': sha(archive), 'cases': baseline_rows})

        # Two-by-two animated review of actual encoded primary outputs.
        font = ImageFont.truetype(str(public/'DejaVuSans.ttf'), 16); frames = []
        review_pictures = {name: decode(public/(name+'.mkv')) for name in ('CA01', 'CA03', 'CA04', 'CA05')}
        for index in range(20):
            canvas = Image.new('RGB', (640, 432), '#151a24'); d = ImageDraw.Draw(canvas)
            for ordinal, name in enumerate(('CA01', 'CA03', 'CA04', 'CA05')):
                x, y = (ordinal % 2)*320, (ordinal // 2)*216
                picture = review_pictures[name][index, ..., :3]
                canvas.paste(Image.fromarray(picture).resize((320, 192)), (x, y+24))
                d.text((x+6, y+3), name+'  '+dict((n, v['type']) for n, v, _ in definitions)[name], font=font, fill='white')
            frames.append(canvas)
        frames[0].save(public/'color-automation.gif', save_all=True, append_images=frames[1:], duration=100, loop=0, optimize=True)
        after = frozen(); assert before == after
        record = {'status': 'passed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                  'elapsed_seconds': time.monotonic()-started, 'frozen_before': before, 'frozen_after': after,
                  'frozen_equal': True, 'generator_sha256': sha(Path(__file__)), 'cases': cases,
                  'cli_calls': len(calls), 'baseline_cli_calls': len(baseline_rows), 'native_calls': len(natives),
                  'main_frames': sum(c['frames'] for c in cases),
                  'stereo_sample_frames': sum(c['stereo_sample_frames'] for c in cases),
                  'independent_rgb_cases': [c['name'] for c in cases if c['rgb_acceptance_applies']],
                  'alpha_glyph_reference': 'same renderer; exact alpha only, RGB acceptance excluded',
                  'continuous_playback_review': False, 'listening_review': False, 'static_review': False,
                  'full_capcut_parity_accepted': False, 'browser_invocations': 0, 'model_forwards': 0, 'virtualization': False,
                  'files': {p.relative_to(public).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
                            for p in sorted(public.rglob('*')) if p.is_file()}}
        save(public/'verification.json', record); save(work/'verification.json', record)
        print(json.dumps({k: record[k] for k in ('status', 'cli_calls', 'baseline_cli_calls', 'main_frames', 'stereo_sample_frames')}))
    except BaseException as exc:
        save(public/'failure.json', {'error': repr(exc), 'frozen_before': before, 'frozen_after': frozen(),
             'generator_sha256': sha(Path(__file__)), 'partial_cases': cases, 'partials_preserved': True})
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True); p.add_argument('--public', type=Path, required=True)
    a = p.parse_args(); run(a.work.resolve(), a.public.resolve())
