"""Original geometry fixture; verify the real CLI against independent pixel math."""
from __future__ import annotations
import argparse, contextlib, copy, hashlib, io, json, socket, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from smoke_fragments import frozen, save, sha
sys.path.insert(0, str(ROOT/'product/src'))
from ai_ad_editor.cli import main
from ai_ad_editor.runtime import configure_local_runtime


def run(public, work):
    assert not public.exists() and not work.exists()
    public.mkdir(parents=True); work.mkdir(parents=True)
    configure_local_runtime(); before = frozen()
    import numpy as np
    from PIL import Image, ImageDraw, ImageSequence
    width, height, count, fps = 160, 120, 16, 8
    y, x = np.mgrid[:height, :width]; px, py = x+.5, y+.5
    truth, bad, sources = [], [], []
    positions = [35+f*2 if f < 8 else 75-(f-8)*2 for f in range(count)]
    for f, a in enumerate(positions):
        # Independent pixel-centre predicates, never mask_edit's rasterizer.
        head = (px-(a+12))**2+(py-17)**2 <= 8**2
        body = (px >= a)&(px < a+24)&(py >= 28)&(py < 65)
        left = (px >= a+3)&(px < a+11)&(py >= 65)&(py < 110)
        right = (px >= a+14)&(px < a+22)&(py >= 65)&(py < 110)
        t = np.clip(((px-a)*-14+(py-34)*31)/(14**2+31**2), 0, 1)
        arm = (px-a+14*t)**2+(py-34-31*t)**2 <= 4**2
        ideal = head|body|left|right|arm
        wrong = head|body|left|(right if not 4 <= f < 12 else False)
        wrong |= (px-138)**2+(py-28)**2 <= 10**2
        wrong |= (px >= 154)&(py >= 112)
        truth.append(ideal); bad.append(wrong)
        rgb = np.empty((height, width, 3), np.uint8)
        rgb[:] = (24, 39, 55); rgb[(x//10+y//10)%2 == 0] = (34, 52, 67)
        rgb[ideal] = (65, 221, 174); sources.append(rgb)
    truth, bad, sources = np.stack(truth), np.stack(bad), np.stack(sources)
    def native(argv, data=None):
        result = subprocess.run(argv, input=data, capture_output=True, timeout=120)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
        return result.stdout
    def encode(path, array, kind='rgba', codec='qtrle'):
        args = ['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'rawvideo', '-pix_fmt', kind,
                '-s', f'{array.shape[2]}x{array.shape[1]}', '-r', str(fps), '-i', 'pipe:0', '-an', '-c:v', codec]
        args += ['-pix_fmt', 'argb', '-video_track_timescale', str(fps)] if codec == 'qtrle' else ['-pix_fmt', 'yuv420p', '-crf', '18', '-movflags', '+faststart']
        native([*args, str(path)], array.tobytes())
    def rgba(alpha):
        array = np.full((*alpha.shape, 4), 255, np.uint8); array[:,:,:,3] = alpha.astype(np.uint8)*255
        return array
    encode(public/'source.mp4', sources, 'rgb24', 'libx264')
    encode(public/'mask-input.mov', rgba(bad)); encode(public/'independent-truth.mov', rgba(truth))
    save(public/'fixture-provenance.json', {'generator': 'scripts/smoke_mask_edits.py', 'generator_sha256': sha(Path(__file__)),
        'license_spdx': 'CC0-1.0', 'original_geometry': True, 'third_party_media': False, 'model_runs': 0,
        'truth': 'independent pixel centre capsule/disk/rectangle predicates before the product is invoked',
        'defects': 'missing arm all frames; missing right leg 4..11; false ellipse and corner; scene cut at frame 8',
        'files': {p.name: sha(p) for p in public.iterdir() if p.is_file()}})
    calls, network = [], []
    def denied(*args, **kwargs):
        network.append('attempted'); raise RuntimeError('fixture host forbids network access')
    socket.create_connection = denied; socket.socket.connect = denied; socket.socket.connect_ex = denied
    def cli(*args, expected=0):
        stream = io.StringIO(); start = time.monotonic()
        with contextlib.redirect_stdout(stream): code = main(list(map(str, args)))
        value = json.loads(stream.getvalue()); number = len(calls)+1
        raw = public/f'cli-{number:02}.log'; raw.write_text(stream.getvalue(), encoding='utf-8', newline='\n')
        calls.append({'number': number, 'args': list(map(str, args)), 'exit_code': code, 'seconds': time.monotonic()-start,
            'log': raw.name, 'sha256': sha(raw)})
        assert code == expected, value
        return value
    project = work/'project'; cli('project', 'init', project)
    asset = cli('media', 'ingest', '--project', project, '--input', public/'mask-input.mov', '--asset-id', 'mask',
        '--license-spdx', 'CC0-1.0', '--evidence', public/'fixture-provenance.json', '--verification-status', 'verified',
        '--permitted-use', 'commercial_ad')['data']['asset']
    def box(a): return [(a+14)/width, 65/height, (a+22)/width, 110/height]
    key_frames = [0, 7, 8, 15]
    edits = {'version': '1.0.0', 'coordinate_space': 'normalized-output', 'scene_cut_frames': [8],
        'mask': {'asset_id': 'mask', 'sha256': asset['sha256'], 'channel': 'alpha', 'width': width, 'height': height,
                 'frames': count, 'fps': str(fps)}, 'operations': [
        {'id': 'leg', 'mode': 'add', 'type': 'rectangle', 'start_frame': 4, 'end_frame': 12, 'interpolation': 'linear',
         'keyframes': [{'frame': f, 'box': box(positions[f])} for f in [4,7,8,11]]},
        {'id': 'arm', 'mode': 'add', 'type': 'brush', 'start_frame': 0, 'end_frame': count, 'interpolation': 'linear',
         'keyframes': [{'frame': f, 'points': [[positions[f]/width, 34/height], [(positions[f]-14)/width, 65/height]],
                       'radius_pixels': 4} for f in key_frames]},
        {'id': 'false-disk', 'mode': 'subtract', 'type': 'ellipse', 'start_frame': 0, 'end_frame': count, 'interpolation': 'hold',
         'keyframes': [{'frame': f, 'box': [128/width, 18/height, 148/width, 38/height]} for f in [0,8]]},
        {'id': 'corner', 'mode': 'intersect', 'type': 'polygon', 'start_frame': 0, 'end_frame': count, 'interpolation': 'hold',
         'keyframes': [{'frame': f, 'points': [[0,0],[1,0],[1,.75],[.8,1],[0,1]]} for f in [0,8]]}]}
    save(public/'edits.json', edits)
    expectation = {'version': '1.0.0', 'coordinate_space': 'normalized-output', 'frames': [
        {'frame': f, 'points': [{'x': (positions[f]+18.5)/width, 'y': 90.5/height, 'expected': 'selected'},
             {'x': (positions[f]-7+.5)/width, 'y': 49.5/height, 'expected': 'selected'},
             {'x': 138.5/width, 'y': 28.5/height, 'expected': 'clear'}, {'x': 157.5/width, 'y': 116.5/height, 'expected': 'clear'}]}
        for f in [0,4,7,8,11,15]]}
    save(public/'expectations.json', expectation)
    failed = cli('quality', 'mask', '--project', project, '--asset-id', 'mask', '--expectations', public/'expectations.json', expected=2)
    save(public/'before-checkpoints.json', failed['data'])
    flags = ('media', 'mask-edit', '--project', project, '--asset-id', 'mask', '--derived-asset-id', 'edited', '--edits', public/'edits.json')
    planned = cli(*flags, '--dry-run')
    result = cli(*flags, '--idempotency-key', 'public-edited'); derived = result['data']['asset']
    replay = cli(*flags, '--idempotency-key', 'public-edited')
    assert replay['data']['asset']['sha256'] == derived['sha256']
    output = project/derived['uri']; (public/'mask-edited.mov').write_bytes(output.read_bytes())
    raw = native(['ffmpeg', '-v', 'error', '-i', str(output), '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1'])
    observed = np.frombuffer(raw, np.uint8).reshape(count, height, width, 4)
    assert np.array_equal(observed, rgba(truth)), int(np.count_nonzero(observed != rgba(truth)))
    passed = cli('quality', 'mask', '--project', project, '--asset-id', 'edited', '--expectations', public/'expectations.json')
    save(public/'after-checkpoints.json', passed['data'])
    stale = copy.deepcopy(edits); stale['mask']['sha256'] = 'sha256:'+'0'*64
    save(work/'stale.json', stale)
    cli('media', 'mask-edit', '--project', project, '--asset-id', 'mask', '--derived-asset-id', 'stale', '--edits', work/'stale.json', expected=2)
    cli('validate', '--project', project); cli('policy', 'audit', '--project', project); cli('rights', 'check', '--project', project)
    cli('convert', 'export', '--project', project, '--target-format', 'package', '--output', public/'editable-project.zip')
    panels = []
    for f in range(count):
        image = Image.new('RGB', (width*3, height+42), '#101c2a'); d = ImageDraw.Draw(image)
        for c, (label, pixels) in enumerate([('SOURCE / ORIGINAL', sources[f]), ('INPUT MASK / FAIL', bad[f]), ('CLI EDIT / EXACT', observed[f,:,:,3] > 127)]):
            if pixels.ndim == 2:
                bg = np.full((height,width,3), [24,39,55], np.uint8); bg[pixels] = [65,221,174]; pixels = bg
            image.paste(Image.fromarray(pixels), (c*width, 20)); d.text((c*width+4, 3), label, fill='white')
        d.text((5,height+25), f'FRAME {f:02}/15 | CUT 8 | 4 SHAPES | AUTHORED MASK / NO MODEL', fill='white')
        panels.append(image)
    encode(public/'comparison.mp4', np.stack([np.asarray(p) for p in panels]), 'rgb24', 'libx264')
    indexed = [p.quantize(colors=96) for p in panels]
    indexed[0].save(public/'comparison.gif', save_all=True, append_images=indexed[1:], duration=[120,130]*8,
        loop=0, disposal=2, optimize=False)
    panels[8].save(public/'contact-frame-08.png')
    with Image.open(public/'comparison.gif') as handle:
        durations = [frame.info['duration'] for frame in ImageSequence.Iterator(handle)]
    assert len(durations) == count and sum(durations) == 2000
    probes = {}
    for path in public.glob('*'):
        if path.suffix in {'.mov','.mp4'}:
            probes[path.name] = json.loads(native(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)]))
            v = next(s for s in probes[path.name]['streams'] if s['codec_type']=='video')
            assert int(v['nb_read_frames']) == count and v['avg_frame_rate']=='8/1'
            native(['ffmpeg','-v','error','-i',str(path),'-f','null','-'])
    assert before == frozen() and network == []
    save(public/'verification.json', {'status':'passed', 'generator_sha256':sha(Path(__file__)), 'product_frozen':before,
        'calls':calls, 'actual_cli_calls':len(calls), 'successful_calls':sum(c['exit_code']==0 for c in calls),
        'expected_rejections':sum(c['exit_code']!=0 for c in calls), 'frames':count, 'fps':fps, 'width':width, 'height':height,
        'independent_rgba_bytes':len(raw), 'independent_rgba_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),
        'all_pixels_exact_to_independent_truth':True, 'every_pts_exact':result['data']['mask_edit']['every_pts_exact'],
        'before_failed_points':len(failed['data']['failed_points']), 'after_checked_points':passed['data']['checked_points'],
        'after_failed_points':len(passed['data']['failed_points']), 'gif_frames':len(durations), 'gif_duration_ms':sum(durations),
        'probes':probes, 'network_guard_events':network, 'model_runs':0, 'browser_started':False, 'virtualization':False,
        'natural_media_published':False, 'continuous_playback_reviewed':False, 'sound_reviewed':False,
        'natural_quality_accepted':False, 'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(public.iterdir()) if p.is_file()}})
    print(json.dumps({'calls':len(calls),'frames':count,'before_failed_points':len(failed['data']['failed_points']),
        'after_passed_points':passed['data']['checked_points'],'independent_exact':True}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--public', type=Path, required=True); p.add_argument('--work', type=Path, required=True)
    args = p.parse_args(); run(args.public.resolve(), args.work.resolve())
