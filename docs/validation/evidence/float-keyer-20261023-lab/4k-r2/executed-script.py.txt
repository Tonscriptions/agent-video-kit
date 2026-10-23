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


def keyer_row(value, parameters):
    """Scalar colour algebra and explicit endpoint tap weights, no production helper."""
    import numpy as np
    def mean(data,radius):
        n=math.floor(radius);fraction=radius-n;out=np.zeros(len(data),np.float64)
        for r,weight in ((n,1-fraction),(n+1,fraction)):
            if weight==0:continue
            for offset in range(-r,r+1):
                indices=np.minimum(len(data)-1,np.maximum(0,np.arange(len(data))+offset))
                out+=data[indices]*(weight/(2*r+1))
        return out
    key=parameters.get('color','#00ff00')
    if isinstance(key,str):key=tuple(int(key[1+i:3+i],16)/255 for i in (0,2,4))
    key=np.asarray(key,np.float64);rgb=value[:,:3].astype(np.float64);delta=rgb-key
    if parameters.get('metric','rgb')=='chroma':
        y=.2126*delta[:,0]+.7152*delta[:,1]+.0722*delta[:,2]
        cb=(delta[:,2]-y)/(2*(1-.0722));cr=(delta[:,0]-y)/(2*(1-.2126))
        distance=np.sqrt((cb*cb+cr*cr)/2)
        distance=mean(distance,parameters.get('chroma_radius',1))
    else:distance=np.sqrt(np.sum(delta*delta,axis=1)/3)
    matte=np.clip((distance-parameters.get('similarity',.1))/parameters['blend'],0,1)
    if parameters.get('invert',False):matte=1-matte
    if parameters.get('feather',0):matte=np.clip(mean(matte,parameters['feather']),0,1)
    result=value.copy();strength=parameters.get('intensity',1.)
    if parameters.get('despill',0):
        axis=int(np.argmax(key));other=[i for i in range(3) if i!=axis]
        spill=np.maximum(rgb[:,axis]-np.max(rgb[:,other],axis=1),0)*parameters['despill']
        if parameters.get('despill_edges',False):spill*=1-matte
        changed=rgb.copy();changed[:,axis]-=spill;changed=changed.astype(np.float32)
        result[:,:3]=rgb*(1-strength)+changed.astype(np.float64)*strength
    result[:,3]=value[:,3].astype(np.float64)*(1-strength+strength*matte)
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
    work = ROOT/'product/.runtime/float-keyer-20261023'/('4k-'+args.revision)
    rel = ROOT/'docs/validation/evidence/float-keyer-20261023-lab'/('4k-'+args.revision)
    assets = ROOT/'docs/assets'/('float-keyer-4k-20261023-'+args.revision)
    for path in (work, rel, assets): path.mkdir(parents=True, exist_ok=False)
    before = frozen(); assert len(before) == 330
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
        project_root, project = create_project(work/'project', 'Original 4K default-budget color key and despill admission fixture', 'float_keyer_4k')
        owned = project_root/'assets/source.mkv'; shutil.copyfile(source, owned)
        project['assets'].append({'id': 'picture', 'kind': 'video', 'uri': 'assets/source.mkv', 'sha256': sha(owned), 'probe': probe_media(owned), 'rights_ref': 'picture'})
        ledger = load_ledger(project_root)
        add_record(ledger, {'asset_id': 'picture', 'verification_status': 'verified', 'source_type': 'generated',
            'source_url': str(source), 'license_spdx': 'CC0-1.0', 'evidence': str(Path(__file__)), 'permitted_uses': ['all'],
            'sha256': sha(owned), 'verified_by': 'synthetic-fixture-generator'})
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
        cases = [('rgb','chroma_key',{'color':'#00ff00','similarity':.06,'blend':.65,'feather':2.375,'intensity':.85}),
                 ('chroma','chromakey',{'color':[.5,.5,.5],'metric':'chroma','matrix':'bt709','range':'full',
                    'chroma_radius':1,'similarity':.04,'blend':.45,'feather':1.25}),
                 ('despill','green_screen',{'color':'#00ff00','similarity':.03,'blend':.75,
                    'feather':.75,'despill':.8,'despill_edges':True})]
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
            mapped = keyer_row(source_row, parameters)
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
                'decoded_Float32_sha256': sha(decoded), 'default_workspace_bytes': 768*1024*1024, 'continuous_key_distance_and_matte': True,
                'preview_receipt': ranged, 'formal_manifest_sha256': sha(formal.with_suffix('.mkv.manifest.json'))})
            if label == 'rgb':
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
        (assets/'LICENSE.txt').write_text('Original synthetic4K color key stripes, rectangle and varying-alpha fixture generated by smoke_float_keyer_4k.py. CC0-1.0. No third-party media, model or likeness. GIF switches three actual single-frame outputs; it is not continuous-motion evidence.\n', encoding='utf8', newline='\n')
        (assets/'author-project.json').write_text(json.dumps(project, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
        (assets/'rights-ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
        check('all330 source inputs unchanged', before == frozen())
        check('no public asset exceeds GitHub100MiB bound', all(p.stat().st_size < 100*1024*1024 for p in assets.iterdir() if p.is_file()))
        record.update(status='passed-actual-default-budget-4K-formal-preview-and-independent-pixels',
            actual_frames_per_case=1, seconds=None, natural_quality_accepted=False, HDR_accepted=False)
    except BaseException as exc:
        record.update(status='failed-preserved', error=repr(exc)); raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), frozen_after=frozen(),
            assets={p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in assets.iterdir() if p.is_file()})
        (rel/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes()); save()
        print(json.dumps({k: record.get(k) for k in ['status', 'error', 'public_CLI_processes']}, ensure_ascii=False), flush=True)


if __name__ == '__main__': main()
