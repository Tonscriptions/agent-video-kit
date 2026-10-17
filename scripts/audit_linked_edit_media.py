"""Re-decode published linked-edit media; validate clocks, pixels and native PCM."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


def run(folder, output):
    import numpy as np
    from PIL import Image
    assert not output.exists()
    sha = lambda p: 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
    def ff(args):
        return subprocess.check_output(['ffmpeg', '-v', 'error', *map(str, args)], timeout=180)
    def probe(path):
        return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(path)], timeout=60))
    def pcm(path):
        return np.frombuffer(ff(['-i', path, '-map', '0:a:0', '-ar', 48000, '-ac', 2, '-f', 'f32le', '-c:a', 'pcm_f32le', 'pipe:1']), np.float32).reshape(-1, 2)
    def video(path):
        stream = next(s for s in probe(path)['streams'] if s['codec_type'] == 'video')
        raw = ff(['-i', path, '-map', '0:v:0', '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'])
        return np.frombuffer(raw, np.uint8).reshape(-1, stream['height'], stream['width'], 3)
    raw = json.loads((folder/'verification.json').read_text(encoding='utf-8'))
    # The generator records the files before writing verification.json itself.
    for name, item in raw['public_files'].items():
        assert sha(folder/name) == item['sha256'], name
    npys = {name: pcm(folder/(name+'.wav')) for name in ('voice', 'sfx', 'bed')}
    cases = []; counts = {'video_files': 0, 'audio_streams': 0, 'all_video_frames': 0}
    inspected = {}
    for p in sorted(folder.iterdir()):
        if p.suffix not in {'.mkv', '.mp4', '.wav'}:
            continue
        info = probe(p); entry = {'sha256': sha(p), 'probe': info}
        if any(s['codec_type'] == 'video' for s in info['streams']):
            frames = video(p); counts['video_files'] += 1; counts['all_video_frames'] += len(frames)
            assert len(frames) == 40, p.name
            v = next(s for s in info['streams'] if s['codec_type'] == 'video')
            assert v['avg_frame_rate'] == '8/1', (p.name, v['avg_frame_rate'])
            assert abs(float(info['format']['duration'])-5.) <= .03, p.name
            entry['decoded_frames'] = len(frames)
            entry['decoded_rgb_sha256'] = 'sha256:'+hashlib.sha256(frames.tobytes()).hexdigest()
        if any(s['codec_type'] == 'audio' for s in info['streams']):
            values = pcm(p); counts['audio_streams'] += 1
            assert np.isfinite(values).all() and abs(len(values)-240000) <= 1024, p.name
            entry['decoded_audio_sample_frames'] = len(values)
        inspected[p.name] = entry
    for index in range(1, 10):
        code = f'L{index:02}'
        actual = video(folder/(code+'-after.mkv')); reference = video(folder/(code+'-reference.mkv'))
        original = video(folder/(code+'-input.mkv'))
        assert np.array_equal(actual, reference)
        model = json.loads((folder/(code+'-reference-project.json')).read_text(encoding='utf-8'))
        samples = np.zeros((240000, 2), np.float64)
        for seq in model['sequences']:
            for t in seq['tracks']:
                if t['kind'] != 'audio' or t.get('muted'):
                    continue
                for c in t['clips']:
                    at = c['timeline_start_tick']*48000//90000
                    start = c['source_in_tick']*48000//90000
                    n = c['duration_tick']*48000//90000
                    samples[at:at+n] += npys[c['asset_id'].removeprefix('audio_')][start:start+n].astype(np.float64)*t.get('audio', {}).get('volume', 1.)
        if index == 9:
            samples = samples[::-1].copy()
        sound = pcm(folder/(code+'-after.mkv'))
        error = float(np.abs(sound.astype(np.float64)-samples).max())
        assert error <= 2e-6, (code, error)
        cue = None
        if index in (7, 8, 9):
            expected_before = list(range(10, 14))
            expected_after = list(range(14, 18))
            if index == 9:
                # The parent reverses an isolated CFR child raster, including
                # its already painted cues: frame j maps to frame N-1-j.
                # This is not a sample at the absent continuous EOF frame N.
                expected_before = sorted(39-j for j in expected_before)
                expected_after = sorted(39-j for j in expected_after)
            observed_before = np.where((original.max(axis=(1, 2, 3)) > 100))[0].tolist()
            observed_after = np.where((actual.max(axis=(1, 2, 3)) > 100))[0].tolist()
            assert observed_before == expected_before, (code, observed_before, expected_before)
            assert observed_after == expected_after, (code, observed_after, expected_after)
            cue = {'expected_before': expected_before, 'observed_before': observed_before,
                   'expected_after': expected_after, 'observed_after': observed_after}
        if index == 6:
            assert np.array_equal(actual[24:40], original[16:32]), 'Nested reverse/keyframes changed on shift'
        if index == 1:
            assert np.array_equal(actual[8:24], original[16:32]), 'Surviving source frames changed'
        for variant in ('input', 'after', 'reference'):
            assert np.array_equal(video(folder/(code+'-'+variant+'.mp4')), video(folder/(code+'-'+variant+'.mkv')))
        cases.append({'id': code, 'video_exact': True, 'max_pcm_error': error, 'cue_frames': cue,
                      'mp4_copied_video_exact': True})
    packages = []
    for code in ('L05', 'L07'):
        with zipfile.ZipFile(folder/(code+'-licensed-project.zip')) as outer:
            notice = outer.read('DejaVu-LICENSE.txt'); assert notice == (folder/'font-license.txt').read_bytes()
            with zipfile.ZipFile(io.BytesIO(outer.read(code+'.aevpkg.zip'))) as z:
                manifest = json.loads(z.read('package-manifest.json'))
                for entry in manifest['files']:
                    data = z.read(entry['path'])
                    assert len(data) == entry['size']
                    assert hashlib.sha256(data).hexdigest() == entry['sha256']
                packages.append({'id': code, 'licensed_wrapper_sha256': sha(folder/(code+'-licensed-project.zip')),
                                 'license_notice_exact': True, 'manifest_entries': len(manifest['files'])})
    with Image.open(folder/'comparison.gif') as im:
        ms = []
        for i in range(im.n_frames):
            im.seek(i); ms.append(im.info.get('duration', 0))
    assert sum(ms) == 5000
    record = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'passed', 'generator_record_sha256': sha(folder/'verification.json'),
              'generator_sha256': sha(Path(__file__).with_name('smoke_linked_edit.py')), 'audit_script_sha256': sha(Path(__file__)),
              'counts': counts, 'cases': cases, 'packages': packages, 'inspected': inspected,
              'gif': {'encoded_frames': len(ms), 'duration_ms': sum(ms)},
              'new_frames': 360, 'new_stereo_sample_frames': 2160000, 'reference_gate': 2e-6,
              'continuous_playback': False, 'listening': False}
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': 'passed', 'cases': len(cases), 'counts': counts, 'gif': record['gif']}, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--folder', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); run(a.folder.resolve(), a.output.resolve())
