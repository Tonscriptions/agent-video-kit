"""Re-decode public library fixtures, raw logs, pixels and PCM independently."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, zipfile
from fractions import Fraction
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')

def raw(path, audio=False):
    flags = ['-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le'] if audio else ['-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo']
    return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), *flags, 'pipe:1'])

def run(public, output):
    record = json.loads((public/'verification.json').read_text(encoding='utf-8'))
    for name, item in record['files'].items():
        assert sha(public/name) == item['sha256'], name
    for name, expected in record['frozen_after'].items():
        assert sha(ROOT/name) == expected, name
    with zipfile.ZipFile(public/'cli-logs.zip') as z:
        calls = json.loads(z.read('calls.json'))
        assert calls == record['calls'] and len(z.namelist()) == 2*len(calls)+1
        for call in calls:
            for stream in ('stdout', 'stderr'):
                payload = z.read(f'{call["index"]:03}.{stream}.log')
                assert 'sha256:'+hashlib.sha256(payload).hexdigest() == call[stream+'_sha256']
            assert call['exit_code'] == call['expected_exit_code']
    checks = []
    for case in record['cases']:
        cid = case['id']; actual = public/(cid+'-actual.mkv'); reference = public/(cid+'-reference.mkv')
        rgb, pcm = raw(actual), raw(actual, True)
        assert rgb == raw(reference) == raw(public/(cid+'-actual.mp4')) == raw(public/(cid+'-reference.mp4'))
        assert 'sha256:'+hashlib.sha256(rgb).hexdigest() == case['rgb_sha256']
        assert 'sha256:'+hashlib.sha256(pcm).hexdigest() == case['pcm_sha256']
        a, b = np.frombuffer(pcm, '<f4'), np.frombuffer(raw(reference, True), '<f4')
        assert a.shape == b.shape and np.isfinite(a).all()
        delta = float(np.max(np.abs(a-b))); assert delta <= 1e-8
        w, h = case['canvas']; assert len(rgb) == case['frames']*w*h*3 and len(a) == 2*case['sample_frames']
        checks.append({'id': cid, 'frames': case['frames'], 'sample_frames': case['sample_frames'],
            'rgb_exact_manual_reference_and_previews': True, 'pcm_max_abs_error': delta})
    videos = audios = 0; probes = {}
    for path in sorted(public.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.mp4', '.mkv', '.wav'}:
            continue
        probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(path)]))
        probes[path.relative_to(public).as_posix()] = probe
        videos += sum(s['codec_type'] == 'video' for s in probe['streams'])
        audios += sum(s['codec_type'] == 'audio' for s in probe['streams'])
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'null', '-'], check=True, capture_output=True)
    for case in record['cases']:
        for suffix in ('actual.mkv', 'reference.mkv', 'actual.mp4', 'reference.mp4'):
            probe = probes[case['id']+'-'+suffix]
            video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            assert [video['width'], video['height']] == case['canvas']
            assert Fraction(video['avg_frame_rate']) == 10 and int(video['nb_read_frames']) == case['frames']
            assert abs(float(probe['format']['duration'])-case['frames']/10) < .05
    with Image.open(public/'comparison.gif') as image:
        gif = {'frames': image.n_frames, 'width': image.width, 'height': image.height,
               'duration_ms': sum((image.seek(i) or image.info.get('duration', 0)) for i in range(image.n_frames))}
    assert gif == {'frames': 20, 'width': 480, 'height': 272, 'duration_ms': 4000}, gif
    frames = np.frombuffer(raw(public/'comparison.mp4'), np.uint8).reshape(-1, 272, 480, 3)
    static = output.parent/'fragments-static-20261018'; static.mkdir(exist_ok=False)
    for index in (0, 20, 39):
        Image.fromarray(frames[index]).save(static/f'frame-{index:02}.png')
    result = {'status': 'passed', 'cases': checks, 'video_streams': videos, 'audio_streams': audios,
        'probes': probes, 'gif': gif, 'static_frames': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in static.glob('*.png')},
        'public_files': len(record['files'])+1, 'public_bytes': sum(p.stat().st_size for p in public.rglob('*') if p.is_file()),
        'public_sha256': {p.relative_to(public).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(public.rglob('*')) if p.is_file()},
        'limits': ['manual_reference_uses_fixed_V36_renderer_not_independent_render_algorithm',
                   'AAC_preview_audio_not_used_as_lossless_reference', 'no_continuous_playback_or_listening',
                   'no_new_model_inference', 'controlled_CC0_fixtures_not_natural_content_or_full_parity']}
    save(output, result)
    print(json.dumps({k: result[k] for k in ('public_files', 'public_bytes', 'video_streams', 'audio_streams', 'gif')}, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--public', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); run(args.public.resolve(), args.output.resolve())
