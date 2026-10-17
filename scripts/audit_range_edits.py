"""Re-decode public V39 media and select fixed V38 author ranges again."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def decode(path, audio=False):
    flags = ['-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le'] if audio else ['-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo']
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), *flags, 'pipe:1'])
    return np.frombuffer(raw, dtype='<f4').reshape(-1, 2) if audio else np.frombuffer(raw, dtype=np.uint8).reshape(-1, 136, 240, 3)


def run(public, output):
    record = json.loads((public/'verification.json').read_text(encoding='utf-8'))
    assert record['status'] == 'passed' and record['frozen_equal'] and record['source_before'] == record['source_after']
    for name, expected in record['source_after'].items():
        assert sha(ROOT/name) == expected, name
    for name, item in record['files'].items():
        assert sha(public/name) == item['sha256'], name
    for call in record['calls']:
        for kind in ('stdout', 'stderr'):
            assert sha(public/f'cli-{call["index"]:03}-{kind}.log') == call[kind+'_sha256']
        assert call['exit_code'] == call['expected_exit_code']
        if call.get('expected_error_code'):
            value = json.loads((public/f'cli-{call["index"]:03}-stdout.log').read_text(encoding='utf-8-sig'))
            assert value['errors'][0]['code'] == call['expected_error_code']
    def media(name):
        return decode(public/(name+'.mkv')), decode(public/(name+'.mkv'), True)
    def cut(pair, a, b=None):
        return pair[0][int(a*10):None if b is None else int(b*10)], pair[1][int(a*48000):None if b is None else int(b*48000)]
    def join(*pairs):
        return tuple(np.concatenate([pair[i] for pair in pairs]) for i in (0, 1))
    new, left, middle, right = [media(name) for name in ('incoming', 'left-author', 'middle-author', 'right-author')]
    processed_child = media('processed-child')
    cases, comparison = [], []
    for row in record['cases']:
        name = row['case']; original = media(name+'-original')
        if name in ('R01', 'R08'):
            expected = join(cut(original, 0, 1), new, cut(original, 1))
        elif name == 'R02':
            expected = join(cut(original, 0, 1), new, cut(original, 2))
        elif name == 'R03':
            expected = join(cut(original, 0, 1), tuple(np.zeros_like(part) for part in new), cut(original, 2))
        elif name == 'R04':
            expected = join(cut(original, 0, 1), cut(original, 2))
        elif name == 'R05':
            expected = join(cut(left, 0, 3), cut(right, 3))
        elif name == 'R06':
            expected = join(cut(left, 0, 1.5), middle, cut(right, 2.5))
        elif name == 'R07':
            expected = join(cut(original, 0, 1), processed_child, cut(original, 1))
        else:
            raise AssertionError(name)
        actual = media(name+'-actual')
        assert np.array_equal(actual[0], expected[0]), name
        assert np.array_equal(actual[1], expected[1]), name
        assert np.isfinite(actual[1]).all()
        assert np.array_equal(decode(public/f'{name}-actual.mp4'), actual[0])
        for label, data in zip(('rgb', 'pcm'), actual):
            assert 'sha256:'+hashlib.sha256(data.tobytes()).hexdigest() == row[label+'_sha256']
        cases.append({'case': name, 'action': row['action'], 'frames': len(actual[0]),
            'stereo_sample_frames': len(actual[1]), 'rgb_and_pcm_exact_fixed_author_selection': True,
            'mp4_picture_exact_mkv': True})
        if name in ('R02', 'R06'):
            comparison.append((expected[0], actual[0]))
    assert not np.array_equal(media('R02-no-motion')[0], media('R02-original')[0])
    assert not np.array_equal(media('R01-original')[0][20:30], media('R08-original')[0][20:30])
    probes, videos, audios = {}, 0, 0
    for path in sorted(public.iterdir()):
        if path.suffix.lower() not in {'.mkv', '.mp4', '.wav'}:
            continue
        result = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-show_streams',
            '-show_format', '-of', 'json', str(path)]))
        probes[path.name] = result
        videos += sum(s['codec_type'] == 'video' for s in result['streams'])
        audios += sum(s['codec_type'] == 'audio' for s in result['streams'])
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'null', '-'], check=True, capture_output=True)
    for case in cases:
        for extension in ('mkv', 'mp4'):
            probe = probes[f'{case["case"]}-actual.{extension}']
            stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            assert (stream['width'], stream['height']) == (240, 136)
            assert Fraction(stream['avg_frame_rate']) == 10 and int(stream['nb_read_frames']) == case['frames']
            assert abs(float(probe['format']['duration'])-case['frames']/10) < .05
    with Image.open(public/'comparison.gif') as picture:
        gif = {'width': picture.width, 'height': picture.height, 'encoded_frames': picture.n_frames,
            'duration_ms': sum(picture.seek(i) or picture.info.get('duration', 0) for i in range(picture.n_frames))}
    assert gif == {'width': 480, 'height': 272, 'encoded_frames': 20, 'duration_ms': 4000}, gif
    stills = [np.concatenate([np.concatenate([reference[frame], actual[frame]], axis=1)
        for reference, actual in comparison], axis=0) for frame in (0, 12, 24, 38)]
    Image.fromarray(np.concatenate((np.concatenate(stills[:2], axis=1), np.concatenate(stills[2:], axis=1)), axis=0)).save(public/'comparison-static.png')
    Image.fromarray(np.concatenate([media('R01-original')[0][22], media('R08-original')[0][22],
        media('R08-actual')[0][32]], axis=1)).save(public/'caption-static.png')
    files = {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in public.iterdir() if p.is_file()}
    result = {'status': 'passed', 'cases': cases, 'cli_count': len(record['calls']),
        'video_streams': videos, 'audio_streams': audios, 'gif': gif, 'probes': probes,
        'public_files': len(files), 'public_bytes': sum(f['bytes'] for f in files.values()), 'public_sha256': files,
        'static_review_candidate': str(public/'comparison-static.png'),
        'limits': ['fixed-same-product-V38-renderer-not-independent-retiming-or-image-oracle',
            'controlled-CC0-counters-not-natural-ad-quality', 'AAC-preview-audio-not-lossless-reference',
            'no-continuous-playback-or-listening', 'no-new-model-inference']}
    save(output, result)
    print(json.dumps({k: result[k] for k in ('status', 'public_files', 'public_bytes', 'video_streams', 'audio_streams', 'gif')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.public.resolve(), args.output.resolve())
