"""Re-decode released files; independent hard-cut/PCM/alpha and declared block references."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path): return digest(path.read_bytes())


def run(public, evidence):
    import numpy as np
    from PIL import Image
    receipt = json.loads((public/'verification.json').read_bytes())
    assert receipt['status'] == 'passed_scoped_magnetic_reorder'
    cases = {row['name']: row for row in receipt['cases']}

    def decoded(name, *, audio=False, alpha=False, width=160, height=64):
        options = ['-c:v', 'libvpx-vp9'] if alpha and not audio else []
        options += ['-i', str(public/name)]
        options += (['-map', '0:a:0', '-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le'] if audio else
                    ['-map', '0:v:0', '-an', '-fps_mode', 'passthrough', '-pix_fmt', 'rgba' if alpha else 'rgb24', '-f', 'rawvideo'])
        result = subprocess.run(['ffmpeg', '-v', 'error', *options, 'pipe:1'], capture_output=True, check=True, timeout=180)
        return (np.frombuffer(result.stdout, dtype='<f4').reshape(-1, 2) if audio else
                np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, height, width, 4 if alpha else 3))

    source, sound = decoded('source-frames.mkv'), decoded('source-audio.wav', audio=True)
    assert source.shape == (60, 64, 160, 3) and set(np.unique(source)) == {0, 255}
    n = np.arange(6*48000)/48000
    expected_sound = np.stack((.05*np.sin(2*np.pi*(120*n+3*n*n))+.015*n,
                               .04*np.cos(2*np.pi*(210*n+2*n*n))-.01*n), axis=1).astype('<f4')
    assert np.array_equal(sound, expected_sound)
    inputs = {'source-frames.mkv': sha(public/'source-frames.mkv'), 'source-audio.wav': sha(public/'source-audio.wav')}
    rows, decoded_cases = [], {}
    for name, row in cases.items():
        alpha = name == 'MR08'
        picture = decoded(row['path'], alpha=alpha, width=row['width'], height=row['height'])
        audio = decoded(row['path'], audio=True)
        assert sha(public/row['path']) == row['output_sha256']
        assert digest(picture.tobytes()) == row['decoded_picture_sha256'] and digest(audio.tobytes()) == row['decoded_pcm_sha256']
        assert len(picture) == row['frames'] and len(audio) == row['stereo_sample_frames'] and np.isfinite(audio).all()
        decoded_cases[name] = (picture, audio)

    for name, order in [('MR01', 'cabd'), ('MR02', 'bdac'), ('MR02-end', 'acbd'), ('MR03', 'cabd'), ('MR06', 'acbd')]:
        expected_picture = np.concatenate([source[(ord(c)-96)*10:(ord(c)-95)*10] for c in order])
        expected_audio = np.concatenate([sound[(ord(c)-96)*48000:(ord(c)-95)*48000] for c in order])
        if name == 'MR03': expected_audio = expected_audio+.1*sound[:4*48000]
        picture, audio = decoded_cases[name]
        assert np.array_equal(picture, expected_picture)
        error = float(np.max(np.abs(audio-expected_audio)));assert error <= 2e-6
        rows.append({'name': name, 'scope': 'independent-original-cut-array', 'rgb_error': 0, 'pcm_error': error,
                     'frames': len(picture), 'independent_pcm_sample_frames': len(audio)})

    # These checks verify unchanged full authors, not the correctness of the
    # original font layout, curve implementation or transition blend itself.
    for name, suffix in [('MR04', 'MR04-before.mkv'), ('MR05', 'MR05-before.mkv'), ('MR07', 'MR07-before.mkv')]:
        row = cases[name];old = decoded(suffix, width=row['width'], height=row['height'])
        if name == 'MR04': slices = [slice(10, 30), slice(0, 10)]
        elif name == 'MR05': slices = [slice(10, 30), slice(0, 10), slice(30, 40)]
        else: slices = [slice(20, 30), slice(0, 20), slice(30, 40)]
        expected = np.concatenate([old[s] for s in slices]);picture, audio = decoded_cases[name]
        assert np.array_equal(picture, expected)
        if name == 'MR07':
            expected_audio = np.concatenate([sound[(ord(c)-96)*48000:(ord(c)-95)*48000] for c in 'cabd'])+.1*sound[:4*48000]
        else:
            old_audio = decoded(suffix, audio=True)
            expected_audio = np.concatenate([old_audio[slice(s.start*4800, s.stop*4800)] for s in slices])
        error = float(np.max(np.abs(audio-expected_audio)));assert error <= 2e-6
        rows.append({'name': name, 'scope': 'same-renderer-original-whole-author-block', 'rgb_error': 0,
                     'pcm_error': error, 'frames': len(picture),
                     'independent_pcm_sample_frames': len(audio) if name == 'MR07' else 0})
    picture, audio = decoded_cases['MR09-package'];old_picture, old_audio = decoded_cases['MR04']
    assert np.array_equal(picture, old_picture) and np.array_equal(audio, old_audio)
    alpha = decoded_cases['MR08'][0][:, :, :, 3]
    y, x = np.indices((64, 160));order = list(range(30, 40))+list(range(10, 30))+list(range(40, 50))
    expected_alpha = np.stack([(x+7*y+19*i) % 256 for i in order]).astype(np.uint8)
    assert np.array_equal(alpha, expected_alpha)
    rows.append({'name': 'MR08', 'scope': 'independent-256-level-source-alpha', 'max_alpha_error': 0,
                 'frames': len(alpha), 'independent_pcm_sample_frames': 0, 'RGBA_RGB_lossless': False})
    rows.append({'name': 'MR09-package', 'scope': 'package-reference', 'frames': len(picture),
                 'rgb_error': 0, 'pcm_error': 0, 'independent_pcm_sample_frames': 0})
    assert sum(row['independent_pcm_sample_frames'] for row in rows) == 1152000
    for row in receipt['calls']:
        index = row['index']
        assert row['exit_code'] == row['expected_exit_code']
        assert sha(evidence/f'{index:03}.stdout.json') == row['stdout_sha256']
        assert sha(evidence/f'{index:03}.stderr.log') == row['stderr_sha256']
    for name, row in receipt['files'].items():
        assert sha(public/name) == row['sha256'] and (public/name).stat().st_size == row['bytes']
    assert sha(ROOT/'scripts/smoke_magnetic_reorder.py') == receipt['generator_sha256']
    assert sha(evidence/'executed-generator.py') == receipt['generator_sha256']
    static_path = evidence/'static-review.json';static = json.loads(static_path.read_bytes())
    assert not static['continuous_playback'] and not static['listening_review']
    for row in static['images']: assert sha(public/row['path']) == row['sha256']
    with Image.open(public/'reorder-before-after.gif') as image:
        duration = 0
        for index in range(image.n_frames): image.seek(index);duration += image.info.get('duration', 0)
        gif = {'frames': image.n_frames, 'duration_ms': duration, 'sha256': sha(public/'reorder-before-after.gif')}
    assert gif['frames'] == 40 and gif['duration_ms'] == 4000
    result = {'status': 'passed_scoped_media_audit', 'cases': rows, 'main_frames': sum(row['frames'] for row in rows),
        'main_stereo_sample_frames': receipt['main_stereo_sample_frames'], 'independent_PCM_sample_frames': 1152000,
        'independent_pure_cut_RGB_frames': 200, 'independent_alpha_frames': 40, 'max_alpha_error': 0,
        'pre_edit_reference_frames': 110, 'source_frames': 60, 'source_PCM_sample_frames': len(sound),
        'inputs': inputs, 'gif': gif, 'static_review_sha256': sha(static_path),
        'public_files': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(public.iterdir()) if p.is_file()},
        'new_model_forwards': 0, 'continuous_playback': False, 'listening_review': False,
        'all_capcut_features_and_quality_accepted': False, 'generator_sha256': sha(Path(__file__))}
    assert result['main_frames'] == 380
    output = evidence/'media-audit.json';assert not output.exists()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: result[k] for k in ('status', 'main_frames', 'independent_PCM_sample_frames', 'max_alpha_error')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True);args = parser.parse_args()
    run(args.public.resolve(), args.evidence.resolve())
