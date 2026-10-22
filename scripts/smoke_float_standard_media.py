"""Reproducible original -> public CLI -> MP4/GIF; optional isolated replay."""
import argparse
import copy
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while block := f.read(1024*1024):
            h.update(block)
    return 'sha256:'+h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision', required=True)
    parser.add_argument('--installed', type=Path)
    parser.add_argument('--reference', type=Path)
    args = parser.parse_args()
    assert args.revision.replace('-', '').isalnum()
    site = args.installed.resolve()/'site' if args.installed else ROOT/'product/src'
    sys.path.insert(0, str(site))
    sys.path.insert(0, str(ROOT/'scripts'))
    from run_frozen_regression import frozen
    import numpy as np
    from PIL import Image, ImageDraw
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.media import ffmpeg_path, probe_media
    from ai_ad_editor.project import create_project, save_project
    from ai_ad_editor.rights import add_record, load_ledger, save_ledger
    configure_local_runtime()
    rel = ROOT/'docs/validation/evidence/float-standard-20261022-lab'/('media-'+args.revision)
    assets = ROOT/'docs/assets'/('float-standard-20261022-'+args.revision)
    work = ROOT/'product/.runtime/float-standard-20261022'/('media-'+args.revision)
    assert not rel.exists() and not assets.exists() and not work.exists()
    rel.mkdir(parents=True); assets.mkdir(parents=True); work.mkdir(parents=True)
    project_root, p = create_project(work/'project', 'Original native float standard render demo', 'float_standard_media')
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'calls': [], 'checks': [], 'network': False, 'virtualization': False, 'browser_tabs': 0,
        'isolated': bool(args.installed), 'script_sha256': sha(Path(__file__)),
        'actual_public_render_CLI_processes': 0, 'full_capcut_parity': False, 'frozen_before': frozen()}
    def save():
        (rel/'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    def check(name, ok, **details):
        record['checks'].append({'name': name, 'ok': bool(ok), **details}); save()
        assert ok, name
    env = dict(os.environ, TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'))
    def run(name, command, **kwargs):
        command = list(map(str, command))
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=600,
                                creationflags=subprocess.CREATE_NO_WINDOW, **kwargs)
        (rel/(name+'.stdout.log')).write_bytes(result.stdout)
        (rel/(name+'.stderr.log')).write_bytes(result.stderr)
        record['calls'].append({'name': name, 'command': command, 'exit_code': result.returncode,
            'stdout_sha256': sha(rel/(name+'.stdout.log')), 'stderr_sha256': sha(rel/(name+'.stderr.log'))}); save()
        assert result.returncode == 0, (name, result.stdout[-2000:].decode('utf8', 'replace'), result.stderr[-2000:].decode('utf8', 'replace'))
        return result.stdout
    if args.installed:
        prefix = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', args.installed.resolve()/'run.py']
    else:
        bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())'
        prefix = [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap, site]
    try:
        w, h, count, fps = 320, 180, 20, 10
        y, x = np.indices((h, w), dtype=np.float64)
        raw = work/'original.gbrap16'
        with raw.open('wb') as f:
            for i in range(count):
                frame = np.ones((h, w, 4), np.float64)
                frame[:, :, :3] = np.stack((.1+.6*x/(w-1), .12+.55*y/(h-1), .15+.45*((x//20+y//20+i//3)%2)), 2)
                left = 12+i*11
                frame[45:130, left:left+60, :3] = [.85, .18+.02*i, .12]
                for bit in range(5):
                    frame[8:20, 8+bit*17:20+bit*17, :3] = .9 if (i>>bit)&1 else .06
                q = np.rint(frame[:, :, [1, 2, 0, 3]]*65535).astype('<u2')
                f.write(np.moveaxis(q, 2, 0).tobytes())
        source = assets/'original.native.mkv'
        run('generate-native-original', [ffmpeg_path(), '-nostdin', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'gbrap16le',
            '-video_size', f'{w}x{h}', '-framerate', fps, '-i', raw, '-c:v', 'ffv1', '-level', '3', '-g', '1', source])
        samples = np.arange(96000, dtype=np.float64)/48000
        pcm = np.stack((.12*np.sin(2*np.pi*347*samples), .11*np.cos(2*np.pi*619*samples)), 1).astype('<f4')
        audio_raw = work/'audio.f32'; audio_raw.write_bytes(pcm.tobytes())
        audio = assets/'original.audio.wav'
        run('generate-original-audio', [ffmpeg_path(), '-nostdin', '-v', 'error', '-f', 'f32le', '-ar', '48000', '-ac', '2', '-i', audio_raw, '-c:a', 'pcm_f32le', audio])
        p['settings']['canvas'].update(width=w, height=h, background='#102040')
        p['settings']['timebase']['display_fps'] = {'num': fps, 'den': 1}
        p['settings']['output'] = {'container': 'mkv', 'video': {'codec': 'libx264', 'preset': 'ultrafast', 'crf': 0, 'pixel_format': 'yuv444p10le'}, 'audio': {'codec': 'pcm_f32le'}}
        signal = {'primaries': 'bt709', 'transfer': 'bt709-oetf'}
        p['settings']['pixel_pipeline'] = {'engine': 'float32-native-v1', 'working_signal': {'primaries': 'bt709', 'transfer': 'linear'},
            'output_signal': signal, 'window_frames': 3, 'max_source_cache_bytes': 4*1024*1024,
            'sources': {'picture': {'source_signal': signal, 'display_geometry': 'square-unrotated'}}}
        ledger = load_ledger(project_root)
        for aid, kind, path in [('picture', 'video', source), ('sound', 'audio', audio)]:
            owned = project_root/'assets'/path.name
            shutil.copyfile(path, owned)
            check(aid+' copied original bytes exact', sha(path) == sha(owned))
            p['assets'].append({'id': aid, 'kind': kind, 'uri': owned.relative_to(project_root).as_posix(), 'sha256': sha(owned), 'probe': probe_media(owned), 'rights_ref': aid})
            add_record(ledger, {'asset_id': aid, 'verification_status': 'verified', 'source_type': 'generated',
                'source_url': str(path), 'license_spdx': 'CC0-1.0', 'evidence': str(Path(__file__)),
                'permitted_uses': ['all'], 'sha256': sha(path), 'verified_by': 'synthetic-fixture-generator'})
        save_ledger(project_root, ledger)
        sequence = p['sequences'][0]; sequence['duration_tick'] = 180000
        base = {'id': 'original_clip', 'asset_id': 'picture', 'timeline_start_tick': 0, 'duration_tick': 180000, 'source_in_tick': 0, 'source_out_tick': 180000}
        sequence['tracks'][0]['clips'] = [base]
        sequence['tracks'][1]['clips'] = [{'id': 'audio_clip', 'asset_id': 'sound', 'timeline_start_tick': 0, 'duration_tick': 180000, 'source_in_tick': 0, 'source_out_tick': 180000}]
        save_project(project_root, p)
        original_settings = copy.deepcopy(p['settings'])
        # Both results below use the public CLI and final standard encoder.
        original = project_root/'renders/original.mkv'
        record['actual_public_render_CLI_processes'] += 1
        orig_result = json.loads(run('public-original-render', [*prefix, 'render', '--project', project_root, '--output', original]))
        check('public original render succeeded', orig_result['ok'])
        overlay = copy.deepcopy(base); overlay.update(id='reverse_circle', reverse=True,
            transform={'scale': .72, 'position': {'x': .5, 'y': .5}},
            blend={'mode': 'screen', 'opacity': .8}, mask={'type': 'circle', 'radius': .45},
            keyframes=[{'property': 'transform.rotation', 'keyframes': [{'at_tick': 0, 'value': -18, 'interpolation': 'linear'}, {'at_tick': 180000, 'value': 18, 'interpolation': 'linear'}]},
                       {'property': 'transform.position.x', 'keyframes': [{'at_tick': 0, 'value': .25, 'interpolation': 'linear'}, {'at_tick': 180000, 'value': .75, 'interpolation': 'linear'}]}])
        sequence['tracks'].append({'id': 'overlay_video', 'kind': 'video', 'order': 1, 'muted': False, 'locked': False, 'clips': [overlay]})
        save_project(project_root, p)
        authored = copy.deepcopy(p)
        output = project_root/'renders/edited.mkv'
        record['actual_public_render_CLI_processes'] += 1
        edited_result = json.loads(run('public-edited-render', [*prefix, 'render', '--project', project_root, '--output', output]))
        check('public edited render succeeded', edited_result['ok'])
        for path in (original, output):
            shutil.copyfile(path, assets/path.name)
            shutil.copyfile(path.with_suffix('.mkv.manifest.json'), assets/(path.name+'.manifest.json'))
        after = json.loads((project_root/'project.json').read_text('utf8'))
        check('author settings clips and source windows unchanged', after['settings'] == original_settings and after['sequences'] == authored['sequences'] and after['assets'] == authored['assets'])
        decoded = {}
        pictures = {}
        for name, path in [('original', original), ('edited', output)]:
            video = run('decode-'+name+'-native-yuv10', [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', path, '-map', '0:v:0', '-an', '-pix_fmt', 'yuv444p10le', '-f', 'rawvideo', 'pipe:1'])
            sound = run('decode-'+name+'-PCM', [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', path, '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1'])
            check(name+' has all 20 encoded frames', len(video) == count*w*h*3*2)
            check(name+' every original stereo PCM sample exact', sound == pcm.tobytes())
            manifest = json.loads(path.with_suffix('.mkv.manifest.json').read_text('utf8'))
            transport = manifest['delivery']['pixel_pipeline']['transport']
            check(name+' closed producer and providers', transport['owned_threads_closed'] and manifest['delivery']['pixel_pipeline']['providers_closed_before_publish'])
            check(name+' finite source window', manifest['delivery']['pixel_pipeline']['source_receipts']['picture']['maximum_cached_float_bytes'] <= 4*1024*1024)
            decoded[name] = {'native_yuv10_sha256': 'sha256:'+hashlib.sha256(video).hexdigest(), 'PCM_sha256': 'sha256:'+hashlib.sha256(sound).hexdigest(), 'manifest': manifest}
            preview = assets/(name+'.mp4')
            run('preview-'+name, [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', path, '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', preview])
            rgb = run('gif-frames-'+name, [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', path, '-map', '0:v:0', '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'])
            pictures[name] = [Image.frombytes('RGB', (w, h), rgb[n*w*h*3:(n+1)*w*h*3]) for n in range(count)]
        check('edited actual encoded picture differs', decoded['original']['native_yuv10_sha256'] != decoded['edited']['native_yuv10_sha256'])
        frames = []
        for n in range(count):
            frame = Image.new('RGB', (w*2, h+28), '#152036')
            frame.paste(pictures['original'][n], (0, 28)); frame.paste(pictures['edited'][n], (w, 28))
            draw = ImageDraw.Draw(frame); draw.text((8, 7), 'ORIGINAL / CLI', fill='white'); draw.text((w+8, 7), 'EDITED / CLI Float32', fill='white')
            frames.append(frame)
        frames[0].save(assets/'comparison.gif', save_all=True, append_images=frames[1:], duration=100, loop=0, optimize=False, disposal=2)
        contact = Image.new('RGB', (w*2, (h+28)*3), '#152036')
        for row, index in enumerate([0, 10, 19]):
            contact.paste(frames[index], (0, row*(h+28)))
        contact.save(assets/'contact.png')
        record['decoded'] = decoded
        record['module_origins'] = {n: str(Path(m.__file__).resolve()) for n, m in sys.modules.items()
            if getattr(m, '__file__', None) and (n.startswith('ai_ad_editor') or n == 'numpy' or n.startswith('numpy.') or n == 'PIL' or n.startswith('PIL.'))}
        check('all product modules from selected site', all(Path(v).is_relative_to(site) for n, v in record['module_origins'].items() if n.startswith('ai_ad_editor')))
        if args.installed:
            check('all isolated third party modules from selected site', all(Path(v).is_relative_to(site) for v in record['module_origins'].values()))
        if args.reference:
            reference = json.loads(args.reference.read_text('utf8'))
            check('isolated real encoded pixels PCM equal source run', all(decoded[n]['native_yuv10_sha256'] == reference['decoded'][n]['native_yuv10_sha256'] and decoded[n]['PCM_sha256'] == reference['decoded'][n]['PCM_sha256'] for n in decoded))
        record['assets'] = {p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in assets.iterdir() if p.is_file()}
        check('298 source inputs unchanged', record['frozen_before'] == frozen() and len(record['frozen_before']) == 298)
        record.update(status='passed-public-CLI-original-and-edited-native-float-media', frames_each=count,
                      stereo_sample_frames_each=96000, continuous_playback_review=False, listening_review=False)
    except BaseException as exc:
        record.update(status='failed-preserved', error=repr(exc)); raise
    finally:
        record['assets'] = {p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in assets.iterdir() if p.is_file()}
        record['finished_at_utc'] = datetime.now(timezone.utc).isoformat(); record['frozen_after'] = frozen(); save()
        (rel/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({k: record.get(k) for k in ['status', 'error', 'actual_public_render_CLI_processes']}), flush=True)


if __name__ == '__main__':
    main()
