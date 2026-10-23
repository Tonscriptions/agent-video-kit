"""Actual default-budget 4K CLI render/preview, independent row mathematics.

The generated image is invariant vertically; a row oracle checks every pixel.
Large decoded Float32 intermediates stay private, outside public Git artifacts.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024*1024): h.update(block)
    return 'sha256:'+h.hexdigest()


def shaper_row(value,parameters):
    from shaper_media_oracle import tables,LOOKS,lookup_1d,lookup_3d
    name=Path(parameters['path']).stem
    first,second,domain,cube_domain=LOOKS[name];one,three=tables()
    result=value.copy();mapped=lookup_1d(value[:,:3],one,first,domain)
    if second:mapped=lookup_3d(mapped,three,second,cube_domain)
    strength=parameters.get('intensity',1.)
    result[:,:3]=value[:,:3].astype('float64')*(1-strength)+mapped.astype('float64')*strength
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--revision', required=True)
    args = parser.parse_args(); assert args.revision.isascii() and args.revision.startswith('r') and args.revision[1:].isdigit()
    sys.path[:0] = [str(ROOT/'product/src'), str(ROOT/'scripts')]
    import numpy as np
    from PIL import Image, ImageDraw
    from run_frozen_regression import frozen
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.media import ffmpeg_path, probe_media
    from ai_ad_editor.project import create_project, save_project
    from ai_ad_editor.rights import add_record, load_ledger, save_ledger
    configure_local_runtime()
    work = ROOT/'product/.runtime/float-shaper-20261023'/('4k-'+args.revision)
    rel = ROOT/'docs/validation/evidence/float-shaper-20261023-lab'/('4k-'+args.revision)
    assets = ROOT/'docs/assets'/('float-shaper-4k-20261023-'+args.revision)
    for path in (work, rel, assets): path.mkdir(parents=True, exist_ok=False)
    before = frozen(); assert len(before) == 331
    record = {'status': 'running', 'pid': os.getpid(), 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'frozen_before': before, 'script_sha256': sha(Path(__file__)), 'calls': [], 'checks': [], 'cases': [],
        'network': False, 'virtualization': False, 'browser_tabs': 0, 'public_CLI_processes': 0,
        'native_windows': True, 'peak_RSS_accepted': False, 'long_duration_accepted': False,
        'continuous_playback_review': False, 'listening_review': False, 'full_capcut_parity': False}
    def save(): (rel/'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    def check(name, ok, **details):
        record['checks'].append({'name': name, 'ok': bool(ok), **details}); save(); assert ok, name
    env = dict(os.environ, TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'))
    def run(name, command):
        command = list(map(str, command)); start = time.monotonic()
        p = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=900, creationflags=subprocess.CREATE_NO_WINDOW)
        (rel/(name+'.stdout.log')).write_bytes(p.stdout); (rel/(name+'.stderr.log')).write_bytes(p.stderr)
        record['calls'].append({'name': name, 'command': command, 'exit_code': p.returncode,
            'seconds': time.monotonic()-start, 'stdout_sha256': sha(rel/(name+'.stdout.log')),
            'stderr_sha256': sha(rel/(name+'.stderr.log'))}); save()
        assert p.returncode == 0, (name, p.stdout[-3000:].decode('utf8', 'replace'), p.stderr[-3000:].decode('utf8', 'replace'))
        return p.stdout
    bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())'
    prefix = [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap, ROOT/'product/src']
    def cli(name, arguments):
        record['public_CLI_processes'] += 1
        result = json.loads(run(name, [*prefix, *arguments])); check(name+' success', result['ok']); return result.get('data', result)
    try:
        width, height = 3840, 2160
        x = np.arange(width, dtype=np.float64)
        row = np.stack((.02+.15*((x//67)%2), .7+.3*x/(width-1), .03+.3*((x//113)%2), .2+.8*x/(width-1)), axis=1)
        row[0, :3] = [.95, .05, .1]; row[1180:1540, :3] = [.85, .25, .12]
        quantized = np.rint(row*65535).astype('<u2'); source_row = quantized.astype(np.float32)/np.float32(65535)
        raw = work/'source.gbrap16'
        with raw.open('wb') as stream:
            for channel in (1, 2, 0, 3):
                line = quantized[:, channel].tobytes()
                for _ in range(height): stream.write(line)
        source = assets/'original.native.mkv'
        run('encode-source', [ffmpeg_path(), '-nostdin', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'gbrap16le',
            '-video_size', f'{width}x{height}', '-framerate', '10', '-i', raw, '-frames:v', '1', '-c:v', 'ffv1', '-level', '3', '-g', '1', source])
        project_root, project = create_project(work/'project', 'Original 4K default-budget standalone 1D and combined shaper LUT admission fixture', 'float_shaper_4k')
        owned = project_root/'assets/source.mkv'; shutil.copyfile(source, owned)
        project['assets'].append({'id': 'picture', 'kind': 'video', 'uri': 'assets/source.mkv', 'sha256': sha(owned), 'probe': probe_media(owned), 'rights_ref': 'picture'})
        ledger = load_ledger(project_root)
        add_record(ledger, {'asset_id': 'picture', 'verification_status': 'verified', 'source_type': 'generated',
            'source_url': str(source), 'license_spdx': 'CC0-1.0', 'evidence': str(Path(__file__)), 'permitted_uses': ['all'],
            'sha256': sha(owned), 'verified_by': 'synthetic-fixture-generator'})
        from shaper_media_oracle import write_tables
        for table in write_tables(project_root/'assets/looks'):
            add_record(ledger,{'asset_id':table.stem,'kind':'lut','verification_status':'verified','source_type':'generated',
                'source_url':str(table),'license_spdx':'CC0-1.0','evidence':str(ROOT/'scripts/shaper_media_oracle.py'),
                'permitted_uses':['all'],'sha256':sha(table),'verified_by':'original-shaper-table-generator'})
        shutil.copytree(project_root/'assets/looks',assets/'original-luts')
        save_ledger(project_root, ledger)
        linear = {'primaries': 'bt709', 'transfer': 'linear'}
        project['settings']['canvas'].update(width=width, height=height, background='#000000')
        project['settings']['timebase']['display_fps'] = {'num': 10, 'den': 1}
        project['settings']['color']['transfer'] = 'linear'
        project['settings']['output'] = {'container': 'mkv', 'video': {'codec': 'libx264', 'preset': 'ultrafast', 'crf': 0, 'pixel_format': 'yuv444p10le'}, 'audio': {'codec': 'pcm_f32le'}}
        project['settings']['pixel_pipeline'] = {'engine': 'float32-native-v1', 'working_signal': dict(linear),
            'output_signal': dict(linear), 'window_frames': 1, 'max_source_cache_bytes': 256*1024*1024,
            'range_policy': 'clip', 'sources': {'picture': {'source_signal': dict(linear), 'display_geometry': 'square-unrotated'}}}
        sequence = project['sequences'][0]; sequence['duration_tick'] = 9000
        base = {'id': 'source', 'asset_id': 'picture', 'timeline_start_tick': 0, 'duration_tick': 9000, 'source_in_tick': 0, 'source_out_tick': 9000}
        from shaper_media_oracle import LOOKS
        cases=[(name,'lut',{'path':'assets/looks/'+name+'.cube','output_signal':dict(linear),
            'interpolation_1d':LOOKS[name][0],'interpolation':LOOKS[name][1] or 'tetrahedral','intensity':.85})
            for name in ('1d_spline','combined','headroom')]
        contacts = []
        for label, kind, parameters in cases:
            e = {'type': kind, 'parameters': {'input_signal':dict(linear),**parameters}}
            sequence['tracks'][0]['clips'] = [dict(base, effects=[e])]
            save_project(project_root, project); authored = copy.deepcopy(project)
            formal = project_root/'renders'/(label+'.mkv')
            public_formal = assets/(label+'.mkv')
            cli('formal-'+label, ['render', '--project', project_root, '--output', formal])
            shutil.copyfile(formal, public_formal)
            shutil.copyfile(formal.with_suffix('.mkv.manifest.json'), public_formal.with_suffix('.mkv.manifest.json'))
            ranged = cli('preview-'+label, ['preview', 'range', '--project', project_root, '--start-frame', 0, '--end-frame', 1, '--height', height, '--output', project_root/('previews/'+label)])
            check(label+' actual unscaled4K preview', ranged['request']['width'] == width and ranged['request']['height'] == height)
            decoded = work/(label+'.gbrapf32')
            run('decode-'+label, [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', ranged['master'], '-map', '0:v:0', '-an', '-pix_fmt', 'gbrapf32le', '-f', 'rawvideo', decoded])
            check(label+' exactly one4K Float32 frame', decoded.stat().st_size == width*height*16)
            planes = np.memmap(decoded, mode='r', dtype='<f4', shape=(4, height, width))
            mapped = shaper_row(source_row, parameters)
            expected = mapped.copy(); expected[:, :3] = (mapped[:, :3].astype(np.float64)*mapped[:, 3:4].astype(np.float64)).astype(np.float32); expected[:, 3] = 1; expected[:, :3] = np.clip(expected[:, :3], 0, 1)
            maximum = 0.; transport_sha = hashlib.sha256()
            for channel, plane_index in enumerate((2, 0, 1, 3)):
                for top in range(0, height, 32):
                    block = planes[plane_index, top:top+32]
                    maximum = max(maximum, float(np.max(np.abs(block.astype(np.float64)-expected[:, channel][None]))))
            check(label+' every4K RGBA component matches independent row mathematics', maximum <= 2e-6,
                compared_components=width*height*4, maximum_absolute_error=maximum, predeclared_tolerance=2e-6)
            for plane_index in range(4):
                for top in range(0, height, 32):
                    transport_sha.update(np.rint(planes[plane_index, top:top+32].astype(np.float64)*65535).astype('<u2').tobytes())
            manifest = json.loads(formal.with_suffix('.mkv.manifest.json').read_bytes())
            check(label+' formal input equals actual Float32 preview after16bit delivery conversion', manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'] == 'sha256:'+transport_sha.hexdigest())
            pcm = work/(label+'.f32')
            run('decode-audio-'+label, [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', formal, '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', pcm])
            check(label+' actual authored silence has4800 stereo samples', pcm.stat().st_size == 4800*8 and not any(pcm.read_bytes()))
            check(label+' source providers and owned transport closed', manifest['delivery']['pixel_pipeline']['providers_closed_before_publish'] and ranged['pixel_pipeline']['transport']['owned_threads_closed'])
            unchanged = json.loads((project_root/'project.json').read_bytes())
            check(label+' authored settings and clips unchanged', unchanged['settings'] == authored['settings'] and unchanged['sequences'] == authored['sequences'])
            shutil.copyfile(ranged['path'], assets/(label+'.mp4')); shutil.copyfile(ranged['manifest'], assets/(label+'.preview.json'))
            viewing = work/(label+'.rgb')
            run('viewing-'+label, [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', ranged['path'], '-map', '0:v:0', '-an', '-vf', 'scale=640:360', '-pix_fmt', 'rgb24', '-f', 'rawvideo', viewing])
            picture = Image.frombytes('RGB', (640, 360), viewing.read_bytes()); ImageDraw.Draw(picture).text((8, 8), 'ACTUAL 4K '+label.upper(), fill='white'); contacts.append(picture)
            record['cases'].append({'name': label, 'parameters': parameters, 'public_formal': str(public_formal.relative_to(ROOT)),
                'actual_resolution': [width, height], 'maximum_absolute_error': maximum, 'compared_components': width*height*4,
                'decoded_Float32_sha256': sha(decoded), 'default_workspace_bytes': 768*1024*1024, 'continuous_1D_and_combined_shaper': True,
                'preview_receipt': ranged, 'formal_manifest_sha256': sha(formal.with_suffix('.mkv.manifest.json'))})
            if label == '1d_spline':
                reused = cli('preview-rgb-reuse', ['preview', 'range', '--project', project_root, '--start-frame', 0, '--end-frame', 1, '--height', height, '--output', project_root/'previews/rgb-reused'])
                check('actual separate4K CLI persistent cache reused', reused['cache_hit'] and reused['cache_key'] == ranged['cache_key'])
                framed = cli('frame-rgb', ['preview', 'frame', '--project', project_root, '--frame', 0, '--height', height, '--output', project_root/'previews/rgb-frame'])
                shutil.copyfile(framed['path'], assets/'rgb-frame.png')
                raw_png = work/'rgb.rgba64'
                run('decode-PNG16-rgb', [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', framed['path'], '-pix_fmt', 'rgba64le', '-f', 'rawvideo', raw_png])
                png = np.memmap(raw_png, mode='r', dtype='<u2', shape=(height, width, 4)); maximum_png = 0
                for top in range(0, height, 32):
                    actual = png[top:top+32].astype(np.int32)
                    reference = np.rint(np.moveaxis(planes[:, top:top+32][[2, 0, 1, 3]], 0, -1).astype(np.float64)*65535).astype(np.int32)
                    maximum_png = max(maximum_png, int(np.max(np.abs(actual-reference))))
                check('actual4K PNG16 matches same Float32 frame', maximum_png <= 1, maximum_RGBA16_code_error=maximum_png)
                del png
            del planes
            save()
        contact = Image.new('RGB', (640, 360*3))
        for index, picture in enumerate(contacts): contact.paste(picture, (0, index*360))
        contact.save(assets/'contact.png')
        contacts[0].save(assets/'comparison.gif', save_all=True, append_images=contacts[1:], duration=800, loop=0, disposal=2)
        (assets/'LICENSE.txt').write_text('Original synthetic4K LUT grading stripes, rectangle and varying-alpha fixture generated by smoke_float_shaper_4k.py. CC0-1.0. No third-party media, model or likeness. GIF switches three actual single-frame outputs; it is not continuous-motion evidence.\n', encoding='utf8', newline='\n')
        (assets/'author-project.json').write_text(json.dumps(project, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
        (assets/'rights-ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
        check('all331 source inputs unchanged', before == frozen() and len(before)==331)
        check('no public asset exceeds GitHub100MiB bound', all(p.stat().st_size < 100*1024*1024 for p in assets.rglob('*') if p.is_file()))
        record.update(status='passed-actual-default-budget-4K-formal-preview-and-independent-pixels',
            actual_frames_per_case=1, seconds=None, natural_quality_accepted=False, HDR_accepted=False)
    except BaseException as exc:
        record.update(status='failed-preserved', error=repr(exc)); raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), frozen_after=frozen(),
            assets={p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in assets.rglob('*') if p.is_file()})
        (rel/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes())
        (rel/'executed-oracle.py.txt').write_bytes((ROOT/'scripts/shaper_media_oracle.py').read_bytes()); save()
        print(json.dumps({k: record.get(k) for k in ['status', 'error', 'public_CLI_processes']}, ensure_ascii=False), flush=True)


if __name__ == '__main__': main()
