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
    rel = ROOT/'docs/validation/evidence/float-levels-20261022-lab'/('media-'+args.revision)
    assets = ROOT/'docs/assets'/('float-levels-20261022-'+args.revision)
    work = ROOT/'product/.runtime/float-levels-20261022'/('media-'+args.revision)
    assert not rel.exists() and not assets.exists() and not work.exists()
    rel.mkdir(parents=True); assets.mkdir(parents=True); work.mkdir(parents=True)
    project_root, p = create_project(work/'project', 'Original native floating RGBA levels and animated exposure demo', 'float_levels_media')
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'calls': [], 'checks': [], 'network': False, 'virtualization': False, 'browser_tabs': 0,
        'isolated': bool(args.installed), 'script_sha256': sha(Path(__file__)),
        'actual_public_render_CLI_processes': 0, 'actual_public_preview_CLI_processes': 0, 'full_capcut_parity': False, 'frozen_before': frozen()}
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
                frame[:, :, :3] *= .6
                frame[:, :, 3] = .2+.8*x/(w-1)
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
        from levels_media_oracle import effects, expected_rgb, METHODS
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
        sequence['tracks'][0]['clips'] = [dict(base,id='look_'+method,timeline_start_tick=i*36000,
            source_in_tick=i*36000,source_out_tick=(i+1)*36000,duration_tick=36000,effects=effects(method))
            for i,method in enumerate(METHODS)]
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
            draw = ImageDraw.Draw(frame); draw.text((8, 7), 'ORIGINAL / CLI', fill='white'); draw.text((w+8, 7), 'LEVELS + ANIMATED EXPOSURE / CLI', fill='white')
            frames.append(frame)
        frames[0].save(assets/'formal-comparison.gif', save_all=True, append_images=frames[1:], duration=100, loop=0, optimize=False, disposal=2)
        contact = Image.new('RGB', (w*2, (h+28)*3), '#152036')
        for row, index in enumerate([0, 10, 19]):
            contact.paste(frames[index], (0, row*(h+28)))
        contact.save(assets/'formal-contact.png')
        record['decoded'] = decoded
        record['module_origins'] = {n: str(Path(m.__file__).resolve()) for n, m in sys.modules.items()
            if getattr(m, '__file__', None) and (n.startswith('ai_ad_editor') or n == 'numpy' or n.startswith('numpy.') or n == 'PIL' or n.startswith('PIL.'))}
        check('all product modules from selected site', all(Path(v).is_relative_to(site) for n, v in record['module_origins'].items() if n.startswith('ai_ad_editor')))
        if args.installed:
            check('all isolated third party modules from selected site', all(Path(v).is_relative_to(site) for v in record['module_origins'].values()))
        if args.reference:
            reference = json.loads(args.reference.read_text('utf8'))
            check('isolated real encoded pixels PCM equal source run', all(decoded[n]['native_yuv10_sha256'] == reference['decoded'][n]['native_yuv10_sha256'] and decoded[n]['PCM_sha256'] == reference['decoded'][n]['PCM_sha256'] for n in decoded))
        # Each call below is a separate public CLI process, including persistent reuse.
        preview_args = ['preview', 'range', '--project', project_root, '--start-frame', 3, '--end-frame', 17, '--height', h]
        record['actual_public_preview_CLI_processes'] += 1
        ranged = json.loads(run('public-preview-range', [*prefix, *preview_args, '--output', project_root/'previews/range3-17']))['data']
        record['actual_public_preview_CLI_processes'] += 1
        framed = json.loads(run('public-preview-frame', [*prefix, 'preview', 'frame', '--project', project_root,
            '--frame', 11, '--height', h, '--output', project_root/'previews/frame11']))['data']
        record['actual_public_preview_CLI_processes'] += 1
        reused = json.loads(run('public-preview-range-reuse', [*prefix, *preview_args,
            '--output', project_root/'previews/range3-17-reused']))['data']
        check('actual separate CLI reused persistent Float32 preview', reused['cache_hit'] and not ranged['cache_hit'] and ranged['cache_key'] == reused['cache_key'])
        for label, result in [('range', ranged), ('frame', framed)]:
            meta = result['pixel_pipeline']
            check(label+' preview providers and producer closed', meta['providers_closed_before_publish'] and meta['transport']['owned_threads_closed'])
            check(label+' preview kept selected author indices', meta['selected_author_frames'] == ([3, 17] if label == 'range' else [11, 12]))
        for source_path, name in [(ranged['path'], 'range.mp4'), (ranged['master'], 'range.master.nut'),
                (ranged['manifest'], 'range.preview.json'), (framed['path'], 'frame.png'), (framed['manifest'], 'frame.preview.json')]:
            shutil.copyfile(source_path, assets/name)
        raw_float = run('decode-actual-preview-Float32-reference', [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', ranged['master'],
            '-map', '0:v:0', '-an', '-pix_fmt', 'gbrapf32le', '-fps_mode', 'passthrough', '-f', 'rawvideo', 'pipe:1'])
        raw_sound = run('decode-actual-preview-PCM', [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', ranged['master'],
            '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1'])
        raw_png = run('decode-actual-preview-PNG16', [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', framed['path'],
            '-an', '-pix_fmt', 'rgba64le', '-f', 'rawvideo', 'pipe:1'])
        check('Float32 preview reference has exact 14 selected frames', len(raw_float) == 14*w*h*16)
        check('preview reference every selected stereo sample exact', raw_sound == pcm[14400:81600].tobytes())
        planes = np.frombuffer(raw_float, '<f4').reshape(14, 4, h, w)
        source_planes = np.frombuffer(raw.read_bytes(), '<u2').reshape(count,4,h,w)
        expected=expected_rgb(source_planes,list(range(3,17)))
        actual_rgb=np.moveaxis(planes[:,[2,0,1]],1,-1)
        difference=float(np.max(np.abs(actual_rgb-expected)))
        check('all selected CLI RGB match independent source-alpha independent endpoint and animated exposure oracle',difference<=5e-7,
            maximum_linear_absolute_error=difference,compared_RGB_values=int(actual_rgb.size))
        check('composited selected alpha remains opaque',np.all(planes[:,3]==1))
        record['levels_oracle']={'maximum_linear_absolute_error':difference,'RGB_values':int(actual_rgb.size),
            'scenarios':list(METHODS),'frames_per_scenario':4,'intensity':'.2 to .85 ease_in_out or direct Bezier;original clip-local author tick','effect_order':'exposure/levels or levels/exposure as authored','animated_channels':['output_black','red_output_white','intensity','amount','black'],
            'source_alpha_gradient':True,'oracle':'independent-source-endpoints-whole-plane-extrema-scalar-preserve-and-exposure-equations',
            'oracle_sha256':sha(ROOT/'scripts/levels_media_oracle.py'),'integer_intermediate':False}
        (assets/'author-project.json').write_text(json.dumps(authored,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        (assets/'rights-ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        (assets/'LICENSE.txt').write_text('Original levels/exposure recipe, synthetic picture and sine-wave audio generated by smoke_float_levels_media.py.\nDedicated to CC0-1.0. No third-party footage, voice, music, model or likeness. Labels use the bundled Pillow default font; no font file is separately redistributed.\n',encoding='utf8',newline='\n')
        rgba = np.moveaxis(planes[8, [2, 0, 1, 3]], 0, -1)
        check('actual Float32 reference finite opaque linear pixels', np.isfinite(rgba).all() and np.all(rgba[:, :, 3] == 1))
        linear = rgba[:, :, :3].astype(np.float64)
        encoded = np.where(linear < .018, 4.5*linear, 1.099*linear**.45-.099).astype(np.float32)
        expected = np.rint(encoded.astype(np.float64)*65535).astype(np.uint16)
        actual_png = np.frombuffer(raw_png, '<u2').reshape(h, w, 4)
        difference = int(np.max(np.abs(actual_png[:, :, :3].astype(np.int32)-expected.astype(np.int32))))
        check('actual PNG16 frame11 matches range author frame11 independent OETF', difference <= 1 and np.all(actual_png[:, :, 3] == 65535), maximum_RGB16_error=difference)
        record['preview_decoded'] = {'reference_frames': 14, 'reference_stereo_sample_frames': 67200,
            'Float32_sha256': 'sha256:'+hashlib.sha256(raw_float).hexdigest(),
            'PCM_sha256': 'sha256:'+hashlib.sha256(raw_sound).hexdigest(),
            'PNG16_sha256': 'sha256:'+hashlib.sha256(raw_png).hexdigest(),
            'reference_signal': ranged['request']['reference_signal'], 'verified_clock': ranged['verified_clock'],
            'range_receipt': ranged, 'frame_receipt': framed, 'reused_receipt': reused}
        rgb = run('decode-actual-preview-viewing-copy', [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', ranged['path'],
            '-map', '0:v:0', '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'])
        check('actual MP4 preview has exact 14 frames', len(rgb) == 14*w*h*3)
        frames = []
        for index in range(14):
            frame = Image.new('RGB', (w*2, h+28), '#152036')
            frame.paste(pictures['original'][index+3], (0, 28))
            frame.paste(Image.frombytes('RGB', (w, h), rgb[index*w*h*3:(index+1)*w*h*3]), (w, 28))
            draw = ImageDraw.Draw(frame)
            draw.text((8, 7), 'ORIGINAL / CLI f3-16', fill='white')
            draw.text((w+8, 7), 'LEVELS + ANIMATED EXPOSURE / PREVIEW', fill='white')
            frames.append(frame)
        frames[0].save(assets/'comparison.gif', save_all=True, append_images=frames[1:], duration=100, loop=0, optimize=False, disposal=2)
        contact = Image.new('RGB', (w*2, (h+28)*3), '#152036')
        for row, index in enumerate([0, 7, 13]): contact.paste(frames[index], (0, row*(h+28)))
        contact.save(assets/'contact.png')
        run('original-selected-range-viewing-copy', [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', original,
            '-vf', 'trim=start_frame=3:end_frame=17,setpts=PTS-STARTPTS',
            '-af', 'atrim=start_sample=14400:end_sample=81600,asetpts=N/SR/TB',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k',
            '-movflags', '+faststart', assets/'original-range.mp4'])
        if args.reference:
            reference = json.loads(args.reference.read_bytes())
            check('isolated actual Float32 PCM PNG16 equal source run', all(record['preview_decoded'][key] == reference['preview_decoded'][key]
                for key in ['Float32_sha256', 'PCM_sha256', 'PNG16_sha256']))
        after_preview = json.loads((project_root/'project.json').read_bytes())
        check('actual previews kept author settings clips and source windows', after_preview['settings'] == authored['settings'] and
            after_preview['sequences'] == authored['sequences'] and after_preview['assets'] == authored['assets'])
        record['assets'] = {p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in assets.iterdir() if p.is_file()}
        check('314 source inputs unchanged', record['frozen_before'] == frozen() and len(record['frozen_before']) == 314)
        record.update(status='passed-public-CLI-floating-levels-and-native-float-previews', frames_each=count,
                      stereo_sample_frames_each=96000, continuous_playback_review=False, listening_review=False)
    except BaseException as exc:
        record.update(status='failed-preserved', error=repr(exc)); raise
    finally:
        record['assets'] = {p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in assets.iterdir() if p.is_file()}
        record['finished_at_utc'] = datetime.now(timezone.utc).isoformat(); record['frozen_after'] = frozen(); save()
        (rel/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes())
        (rel/'executed-oracle.py.txt').write_bytes((ROOT/'scripts/levels_media_oracle.py').read_bytes())
        print(json.dumps({k: record.get(k) for k in ['status', 'error', 'actual_public_render_CLI_processes', 'actual_public_preview_CLI_processes']}), flush=True)


if __name__ == '__main__':
    main()
