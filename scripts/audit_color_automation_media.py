"""Audit encoded color-animation masters, previews, clocks and static review sheets."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
def digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path): return digest(path.read_bytes())
def read(path): return json.loads(path.read_bytes())
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

def run(public, output):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont, ImageSequence
    assert not output.exists(); r = read(public/'verification.json'); current = frozen()
    assert r['frozen_before'] == r['frozen_after'] == current and len(current) == 186
    assert len(r['cases']) == 14 and r['main_frames'] == 262 and r['stereo_sample_frames'] == 1158528
    assert sha(ROOT/'scripts/smoke_color_automation.py') == sha(public/'executed-generator.py')
    for name, row in r['files'].items():
        p = public/name; assert p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], p
    natives = []; previews = []; masters = []; pictures = {}
    def native(command):
        done = subprocess.run(command, capture_output=True, check=True, timeout=120)
        natives.append({'command': command, 'exit_code': done.returncode,
                        'stdout_sha256': digest(done.stdout), 'stderr_sha256': digest(done.stderr)})
        return done.stdout
    def probe(path):
        return json.loads(native(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(path)]))
    for row in r['cases']:
        name = row['name']; path = public/row['output']; alpha = name == 'CA12'; prefix = ['-c:v', 'libvpx-vp9'] if alpha else []
        raw = native(['ffmpeg', '-v', 'error', *prefix, '-i', str(path), '-map', '0:v:0', '-an',
                      '-fps_mode', 'passthrough', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1'])
        assert digest(raw) == row['decoded_rgba_sha256']
        pixels = np.frombuffer(raw, 'u1').reshape(-1, 96, 160, 4); pictures[name] = pixels
        reference = np.load(public/(name+'-reference.npz'))['rgba']
        rgb = int(np.abs(pixels[..., :3].astype('i2')-reference[..., :3].astype('i2')).max())
        ae = int(np.abs(pixels[..., 3].astype('i2')-reference[..., 3].astype('i2')).max())
        assert rgb == row['max_rgb_error'] and ae == row['max_alpha_error'] == 0
        if row['rgb_acceptance_applies']: assert rgb <= 2
        pcm = native(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0', '-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le', 'pipe:1'])
        assert digest(pcm) == row['decoded_pcm_sha256'] and len(pcm) == row['stereo_sample_frames']*8
        master = probe(path); v = next(s for s in master['streams'] if s['codec_type'] == 'video')
        assert int(v['nb_read_frames']) == row['frames'] and (int(v['width']), int(v['height'])) == (160, 96)
        masters.append({'path': path.name, 'sha256': sha(path), 'probe': master,
                        'decoded_rgba_sha256': digest(raw), 'decoded_pcm_sha256': digest(pcm)})
        path = public/(name+'.mp4'); preview = probe(path)
        v = next(s for s in preview['streams'] if s['codec_type'] == 'video')
        a = next(s for s in preview['streams'] if s['codec_type'] == 'audio'); rate = Fraction(row['fps'])
        assert (int(v['width']), int(v['height'])) == (160, 96) and Fraction(v['avg_frame_rate']) == rate
        assert int(v['nb_read_frames']) == row['frames'] and Fraction(v['start_time']) == Fraction(a['start_time']) == 0
        assert abs(Fraction(v['duration'])-Fraction(row['frames'], 1)/rate) <= Fraction(1, 1000000)
        assert abs(Fraction(a['duration'])-Fraction(row['stereo_sample_frames'], 48000)) <= Fraction(1, 48000)
        pts = json.loads(native(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
            '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(path)]))['frames']
        assert len(pts) == row['frames']
        assert all(abs(Fraction(f['best_effort_timestamp_time'])-Fraction(i, 1)/rate) <= Fraction(1, 1000000) for i, f in enumerate(pts))
        previews.append({'path': path.name, 'sha256': sha(path), 'probe': preview, 'frames': len(pts),
            'video_coverage_seconds': float(Fraction(row['frames'], 1)/rate),
            'audio_seconds': row['stereo_sample_frames']/48000,
            'authored_seconds': row['duration_tick']/90000, 'pts_checked': True})
    with Image.open(public/'color-automation.gif') as gif:
        durations = [f.info.get('duration', 0) for f in ImageSequence.Iterator(gif)]
        assert gif.size == (640, 432) and len(durations) == 20 and sum(durations) == 2000
    font = ImageFont.truetype(str(public/'DejaVuSans.ttf'), 15); sheets = []
    groups = [('encoded-static-review.png', [(name, frame) for name in ('CA01', 'CA03', 'CA04', 'CA05') for frame in (0, 9, 19)]),
        ('timeline-static-review.png', [('CA06', 8), ('CA06', 18), ('CA07', 14), ('CA08', 6), ('CA09', 6),
            ('CA10', 4), ('CA11', 15), ('CA12', 5), ('CA13', 1)])]
    for filename, selected in groups:
        sheet = Image.new('RGB', (960, 216*((len(selected)+2)//3)), '#151a24'); d = ImageDraw.Draw(sheet); items = []
        for i, (name, index) in enumerate(selected):
            pixels = pictures[name][index]; image = Image.fromarray(pixels)
            if name == 'CA12':
                checker = Image.new('RGBA', (160, 96), '#4d5666'); grid = ImageDraw.Draw(checker)
                for y in range(0, 96, 12):
                    for x in range(0, 160, 12):
                        if (x//12+y//12) % 2: grid.rectangle((x, y, x+11, y+11), fill='#c4cbd6')
                image = Image.alpha_composite(checker, image)
            x, y = (i % 3)*320, (i//3)*216
            sheet.paste(image.convert('RGB').resize((320, 192), Image.Resampling.NEAREST), (x, y+24))
            d.text((x+7, y+4), f'{name} actual master frame {index}', font=font, fill='white')
            items.append({'case': name, 'frame': index, 'rgba_sha256': digest(pixels.tobytes()), 'checkerboard_alpha': name == 'CA12'})
        sheet.save(public/filename); sheets.append({'path': filename, 'sha256': sha(public/filename), 'items': items})
    source_probe = probe(public/'source.mkv'); source_v = next(s for s in source_probe['streams'] if s['codec_type'] == 'video')
    assert int(source_v['nb_read_frames']) == 40 and Fraction(source_v['avg_frame_rate']) == 10
    save(output.with_name('media-native-calls.json'), natives)
    assert frozen() == current
    record = {'status': 'passed_scoped_media_audit', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'generator_sha256': sha(Path(__file__)), 'source_receipt_sha256': sha(public/'verification.json'),
        'masters': masters, 'previews': previews, 'source': {'path': 'source.mkv', 'sha256': sha(public/'source.mkv'), 'probe': source_probe},
        'master_frames': r['main_frames'], 'master_stereo_sample_frames': r['stereo_sample_frames'],
        'gif': {'width': 640, 'height': 432, 'frames': len(durations), 'duration_ms': sum(durations), 'sha256': sha(public/'color-automation.gif')},
        'static_review_sheets': sheets, 'static_review_performed': False, 'continuous_playback': False, 'human_listening': False,
        'native_calls': len(natives), 'frozen_before': current, 'frozen_after': frozen(), 'other_machine_accepted': False}
    save(output, record)
    print(json.dumps({k: record[k] for k in ('status', 'master_frames', 'master_stereo_sample_frames', 'gif')}))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--public', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); run(a.public.resolve(), a.output.resolve())
