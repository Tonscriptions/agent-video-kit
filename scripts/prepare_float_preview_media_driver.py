"""Extend the frozen, already exercised original-media driver for real previews."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-standard-render-lab-20261022'


def main():
    source = PARENT/'scripts/smoke_float_standard_media.py'
    owner = json.loads((PARENT/'product/.runtime/float-standard-20261022/complete-r1/run.json').read_bytes())
    assert owner['verification_scripts']['scripts/smoke_float_standard_media.py'] == 'sha256:'+hashlib.sha256(source.read_bytes()).hexdigest()
    text = source.read_text('utf8').replace('float-standard-20261022', 'float-preview-20261022')
    text = text.replace('Original native float standard render demo', 'Original native float timeline preview demo')
    text = text.replace("'float_standard_media'", "'float_preview_media'")
    text = text.replace("'actual_public_render_CLI_processes': 0,", "'actual_public_render_CLI_processes': 0, 'actual_public_preview_CLI_processes': 0,")
    text = text.replace("assets/'comparison.gif'", "assets/'formal-comparison.gif'").replace("assets/'contact.png'", "assets/'formal-contact.png'")
    anchor = "        record['assets'] = {p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in assets.iterdir() if p.is_file()}\n        check('298 source inputs unchanged', record['frozen_before'] == frozen() and len(record['frozen_before']) == 298)"
    assert text.count(anchor) == 1
    addition = '''        # Each call below is a separate public CLI process, including persistent reuse.
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
            draw.text((w+8, 7), 'ACTUAL CLI PREVIEW / Float32', fill='white')
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
        check('300 source inputs unchanged', record['frozen_before'] == frozen() and len(record['frozen_before']) == 300)'''
    text = text.replace(anchor, addition)
    text = text.replace("status='passed-public-CLI-original-and-edited-native-float-media'", "status='passed-public-CLI-original-edited-and-native-float-previews'")
    text = text.replace("'actual_public_render_CLI_processes']}), flush=True)", "'actual_public_render_CLI_processes', 'actual_public_preview_CLI_processes']}), flush=True)")
    target = ROOT/'scripts/smoke_float_preview_media.py'; assert not target.exists()
    target.write_text(text, encoding='utf8', newline='\n')
    print(json.dumps({'status': 'prepared-original-and-actual-preview-CLI-media-driver',
        'parent_driver_sha256': 'sha256:'+hashlib.sha256(source.read_bytes()).hexdigest(),
        'driver_sha256': 'sha256:'+hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
