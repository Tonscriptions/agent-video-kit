"""Render measured timestamp charts, explicitly research rather than product output."""
import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    from PIL import Image, ImageDraw, ImageFont
    import PIL
    folder = args.output.resolve()
    assert folder.is_relative_to(ROOT / 'docs/assets')
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    fixture = args.fixture.resolve()
    truth = json.loads((fixture / 'input-provenance.json').read_bytes())
    source = fixture / 'input.wav'
    with wave.open(str(source), 'rb') as stream:
        assert (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) == (16000, 1, 2)
        pcm = stream.readframes(stream.getnframes())
    samples = array('h', pcm)
    if sys.byteorder != 'little':
        samples.byteswap()
    assert len(samples) == truth['samples']
    duration = len(samples) / 16000
    rows = [('REFERENCE BLOCKS', (159, 172, 191), [
        {'text': r['word'], 'a': r['start_sample'] / 16000, 'b': r['end_sample'] / 16000}
        for r in truth['words']])]
    dependencies = [{'path': str(fixture / 'input-provenance.json'), 'sha256': digest(fixture / 'input-provenance.json')}]
    for label, raw in args.candidate:
        path = Path(raw).resolve()
        data = json.loads(path.read_bytes())
        if 'short' in data and data['short'].get('format') == 'agent-ctc-alignment-v1':
            historical = data['short']
            assert historical['source_sha256'].removeprefix('sha256:') == digest(source)
            case = {'samples': historical['samples'], 'posthoc_timestamp_fix_applied': False,
                    'units': [{'text': u['text'], 'raw_start_ms': u['start_sample'] / 16,
                               'raw_end_ms': u['end_sample'] / 16} for u in historical['segments'][0]['units']]}
            dependencies.append({'historical_inference_reused': True, 'new_forward_calls': 0})
        else:
            assert data['status'] == 'inference_succeeded'
            case = next(c for c in data['cases'] if c['audio']['path'] == str(source))
        assert case['samples'] == len(samples) and not case['posthoc_timestamp_fix_applied']
        rows.append((label, [(54, 189, 222), (240, 180, 61), (237, 110, 151)][len(rows) - 1],
            [{'text': r['text'], 'a': r['raw_start_ms'] / 1000, 'b': r['raw_end_ms'] / 1000} for r in case['units']]))
        dependencies.append({'path': str(path), 'sha256': digest(path)})
    assert len(rows) <= 4
    for _, _, spans in rows:
        assert [s['text'] for s in spans] == [w['word'] for w in truth['words']]
    font_path = ROOT / 'docs/assets/html-quality-20261018/inputs/complete-font.ttf'
    if not font_path.is_file():
        font_path = ROOT / 'docs/assets/ctc-alignment-20261018/font.ttf'
    font = ImageFont.truetype(str(font_path), 22)
    small = ImageFont.truetype(str(font_path), 17)
    image = Image.new('RGB', (1280, 720), (13, 25, 43))
    draw = ImageDraw.Draw(image)
    draw.text((38, 27), 'OFFLINE BOUNDARY RESEARCH', font=font, fill=(233, 242, 252))
    draw.text((38, 70), 'ACTUAL MODEL TIMES / NO FIXED PADDING', font=small, fill=(157, 189, 214))
    draw.text((38, 105), 'REFERENCE = AUTHORED BLOCKS / NOT PHONETIC TRUTH', font=small, fill=(157, 189, 214))
    x0, x1 = 45, 1230
    def x(seconds):
        return round(x0 + seconds / duration * (x1 - x0))
    for i in range(x1 - x0):
        a, b = i * len(samples) // (x1 - x0), (i + 1) * len(samples) // (x1 - x0)
        amplitude = max(abs(v) for v in samples[a:max(a + 1, b)]) / 32768
        height = round(amplitude * 55)
        draw.line((x0 + i, 218 - height, x0 + i, 218 + height), fill=(70, 170, 190))
    for i, (label, color, spans) in enumerate(rows):
        y = 293 + i * 90
        draw.text((x0, y - 25), label, font=small, fill=color)
        draw.line((x0, y + 27, x1, y + 27), fill=(48, 61, 79))
        for span in spans:
            a, b = x(span['a']), x(span['b'])
            if b > a:
                draw.rectangle((max(x0, a), y, min(x1, b), y + 25), fill=color)
                draw.text((max(x0, a) + 2, y + 32), span['text'], font=small, fill=(217, 229, 240))
            else:
                draw.line((a, y - 5, a, y + 29), fill=(255, 48, 48), width=3)
    draw.text((38, 677), 'MEASUREMENT VISUALIZATION / PRODUCT ALIGNER UNCHANGED', font=small, fill=(165, 182, 204))
    image.save(folder / 'chart.png')
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    assert ffmpeg and ffprobe
    frames = math.ceil(duration * 30)
    command = [ffmpeg, '-v', 'error', '-nostdin', '-n', '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', '1280x720',
        '-framerate', '30', '-i', 'pipe:0', '-i', str(source), '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-crf', '18',
        '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', str(folder / 'comparison.mkv')]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    gifs = []
    try:
        for frame in range(frames):
            pic = image.copy()
            d = ImageDraw.Draw(pic)
            at = x(frame / 30)
            d.line((at, 155, at, 645), fill=(255, 255, 255), width=2)
            process.stdin.write(pic.tobytes())
            if frame % 3 == 0:
                gifs.append(pic.resize((640, 360)))
        process.stdin.close()
        stderr = process.stderr.read()
        assert process.wait(timeout=60) == 0, stderr.decode('utf-8', 'replace')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    gifs[0].save(folder / 'comparison.gif', save_all=True, append_images=gifs[1:], duration=100, loop=0)
    subprocess.run([ffmpeg, '-v', 'error', '-nostdin', '-n', '-i', str(folder / 'comparison.mkv'),
        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(folder / 'comparison.mp4')], check=True, capture_output=True)
    raw = subprocess.run([ffmpeg, '-v', 'error', '-nostdin', '-i', str(folder / 'comparison.mkv'), '-map', '0:a',
        '-f', 's16le', 'pipe:1'], check=True, capture_output=True).stdout
    assert raw == pcm
    probe = json.loads(subprocess.run([ffprobe, '-v', 'error', '-select_streams', 'v:0', '-show_frames',
        '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(folder / 'comparison.mkv')],
        check=True, capture_output=True).stdout)
    assert len(probe['frames']) == frames
    assert all(abs(float(f['best_effort_timestamp_time']) - i / 30) <= .000501 for i, f in enumerate(probe['frames']))
    for index in [0, frames // 2, frames - 1]:
        subprocess.run([ffmpeg, '-v', 'error', '-nostdin', '-n', '-i', str(folder / 'comparison.mkv'),
            '-vf', f'select=eq(n\\,{index})', '-frames:v', '1', str(folder / f'frame-{index:03}.png')], check=True, capture_output=True)
    report = {'status': 'verified', 'research_measurement_not_product_render': True, 'frames': frames,
        'fps': 30, 'samples': len(samples), 'sample_rate': 16000, 'pcm_equal_to_original': True,
        'pcm_sha256': hashlib.sha256(pcm).hexdigest(), 'all_video_pts_checked': True,
        'gif_frames': len(gifs), 'gif_duration_ms': len(gifs) * 100, 'source_duration_seconds': duration,
        'pillow_version': PIL.__version__, 'font': str(font_path), 'font_sha256': digest(font_path),
        'dependencies': dependencies, 'command': command, 'generator_sha256': digest(Path(__file__)),
        'continuous_playback_review': False, 'listening_review': False, 'static_review': False,
        'files': {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(folder.iterdir()) if p.is_file()}}
    (folder / 'verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'frames': frames, 'samples': len(samples), 'gif_frames': len(gifs)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate', nargs=2, action='append', required=True)
    main(parser.parse_args())
