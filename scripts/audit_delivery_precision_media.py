"""Audit retained native media/receipts without calling product clock helpers."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return 'sha256:'+hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                    encoding='utf-8', newline='\n')


def run(public, evidence):
    import numpy as np
    from PIL import Image

    output = evidence/'media-audit.json'
    assert not output.exists()
    smoke = json.loads((public/'verification.json').read_bytes())
    assert smoke['frozen_after'] == smoke['frozen_before'] == frozen()
    installation = json.loads((ROOT/'docs/validation/evidence/delivery-precision-native-install-20261018/verification.json').read_bytes())
    assert installation['status'] == 'passed' and installation['frozen_after'] == frozen()
    assert sha(public/'agent-video-kit-cp313-win_amd64.zip') == installation['release_zip_sha256']
    for call in smoke['calls']:
        index = call['index']
        assert sha(evidence/f'{index:03}.stdout.json') == call['stdout_sha256']
        assert sha(evidence/f'{index:03}.stderr.log') == call['stderr_sha256']
        assert call['exit_code'] == call['expected_exit_code']
    assert sha(evidence/'executed-generator.py') == smoke['generator_sha256']
    assert sha(ROOT/'scripts/smoke_delivery_precision.py') == smoke['generator_sha256']

    def decode(path, *, width=256, height=64, decoder=None, audio=False):
        options = ['-c:v', decoder] if decoder and not audio else []
        output_args = (['-map', '0:a:0', '-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le'] if audio else
                       ['-map', '0:v:0', '-an', '-fps_mode', 'passthrough', '-pix_fmt', 'rgba', '-f', 'rawvideo'])
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', *options, '-i', str(path), *output_args, 'pipe:1'])
        return (np.frombuffer(raw, dtype='<f4').reshape(-1, 2) if audio else
                np.frombuffer(raw, dtype=np.uint8).reshape(-1, height, width, 4))

    source = decode(public/'source-ramp.mkv')
    original = decode(public/'source-audio.wav', audio=True)
    held = np.concatenate((source[:5], np.repeat(source[4:5], 4, axis=0), source[5:]))
    sound = np.concatenate((original[:24000], np.zeros((19200, 2), dtype='<f4'), original[24000:]))
    pictures, audio = {}, {}
    for row in smoke['cases']:
        path = public/row['path']
        assert sha(path) == row['output_sha256']
        picture = decode(path, width=row['width'], height=row['height'], decoder=row['decoder'])
        samples = decode(path, audio=True)
        assert len(picture) == row['frames'] and len(samples) == row['stereo_sample_frames']
        assert digest(picture.tobytes()) == row['decoded_rgba_sha256']
        assert digest(samples.tobytes()) == row['decoded_pcm_sha256']
        pictures[row['name']], audio[row['name']] = picture, samples
    assert len(source) == 12 and len(held) == 16
    for name in ('DP01', 'DP02'):
        assert np.array_equal(pictures[name][:, :, :, 3], held[:, :, :, 3])
    assert np.array_equal(pictures['DP07'][:, :, :, 3], pictures['DP06'][:, :, :, 3])
    assert np.array_equal(audio['DP00'], sound) and len(sound) == 76800
    original_rgb = held[:, :, :, :3].astype(float)*held[:, :, :, 3:4]/255
    rgb_errors = {'DP00': float(np.abs(pictures['DP00'][:, :, :, :3].astype(float)-original_rgb).max())}
    for name, background in (('DP03', 16), ('DP04', 240)):
        a = pictures['DP01'][:, :, :, 3:4].astype(float)/255
        expected = pictures['DP01'][:, :, :, :3]*a+background*(1-a)
        rgb_errors[name] = float(np.abs(pictures[name][:, :, :, :3].astype(float)-expected).max())
    assert all(error <= 3 for error in rgb_errors.values())
    assert np.array_equal(pictures['DP09'], pictures['DP10'])
    assert np.array_equal(audio['DP09'], audio['DP10'])
    assert len(audio['DP08']) == 192480 and len(audio['DP09']) == 192512
    for row in smoke['negative_controls']:
        if row['new_native_media']:
            assert sha(public/row['path']) == row['output_sha256']
        assert any(error['code'] == 'OUTPUT_AV_SYNC_OUT_OF_RANGE' for error in row['errors'])
    gif_rows = []
    for row in smoke['gifs']:
        path = public/row['name']
        assert sha(path) == row['sha256']
        with Image.open(path) as image:
            duration = 0
            for index in range(image.n_frames):
                image.seek(index)
                duration += image.info.get('duration', 0)
            assert image.n_frames == row['image_frames'] and duration == row['duration_ms']
            gif_rows.append(row)
    review = {'method': 'assistant inspected both local contact PNGs with view_image after actual rendering',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'images': [{'path': 'alpha-contact.png', 'sha256': sha(public/'alpha-contact.png'),
                    'source_output_frame_indices': [4, 7, 9, 15],
                    'observations': 'labels legible; held child unchanged at .4/.7 seconds; colour/alpha bands advance after resume; one-level alpha error is established by measurements, not visual judgement'},
                   {'path': 'fractional-contact.png', 'sha256': sha(public/'fractional-contact.png'),
                    'source_output_frame_indices': [9, 15, 25, 40],
                    'observations': 'parent brightness changes; diagnostic LOCAL CUT overlaps original counter; last frame black matches root extension past original 4-second content'}],
        'static_moments_checked': 8, 'continuous_playback': False, 'listening_review': False,
        'natural_advertising_layout_accepted': False, 'overall_capcut_quality_accepted': False}
    save(evidence/'static-review.json', review)
    value = {'status': 'passed_scoped_media_audit', 'main_frames': sum(row['frames'] for row in smoke['cases']),
        'main_stereo_sample_frames': sum(row['stereo_sample_frames'] for row in smoke['cases']),
        'independent_original_pcm_sample_frames': 76800, 'max_independent_rgb_errors': rgb_errors,
        'lossless_original_alpha_max_error': 0, 'lossy_alpha_exact_accepted': False,
        'gifs': gif_rows, 'static_review_sha256': sha(evidence/'static-review.json'),
        'public_files': {path.name: {'sha256': sha(path), 'bytes': path.stat().st_size}
                         for path in sorted(public.iterdir()) if path.is_file()},
        'verification_sha256': sha(public/'verification.json'), 'generator_sha256': sha(Path(__file__)),
        'rendered_new_frames': 0, 'new_model_forwards': 0, 'browser_invocations': 0}
    save(output, value)
    print(json.dumps({key: value[key] for key in ('status', 'main_frames', 'main_stereo_sample_frames',
                                                'independent_original_pcm_sample_frames')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    run(args.public.resolve(), args.evidence.resolve())
