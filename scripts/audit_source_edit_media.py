"""Re-decode published source-edit comparisons and verify all artifact bytes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from smoke_fragments import frozen, save, sha


def run(public, output):
    import numpy as np
    from PIL import Image

    assert not output.exists()
    record = json.loads((public/'verification.json').read_text(encoding='utf-8'))
    assert record['status'] == 'passed' and record['case_count'] == 9
    assert record['source_before'] == record['source_after'] == frozen()
    assert record['worker_processes_exited']
    for name, item in record['files'].items():
        assert sha(public/name) == item['sha256'], name
    calls = record['cli_calls']
    assert len(calls) == record['cli_count']
    for item in calls:
        index = item['index']
        assert sha(public/f'cli-{index:03}-stdout.log') == item['stdout_sha256']
        assert sha(public/f'cli-{index:03}-stderr.log') == item['stderr_sha256']
        assert item['exit_code'] == item['expected_exit_code']

    streams = []
    for movie in sorted(public.iterdir()):
        if movie.suffix.lower() not in {'.mp4', '.mkv', '.wav'}: continue
        result = subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
            '-show_entries', 'format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,nb_read_frames,sample_rate,channels',
            '-of', 'json', str(movie)])
        streams.append({'file': movie.name, **json.loads(result)})

    def decode(path, kind):
        flags = ['-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo'] if kind == 'rgb' else ['-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le']
        return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), *flags, 'pipe:1'])

    cases = []
    identities = []
    source = np.frombuffer(decode(public/'source-a.mp4', 'rgb'), np.uint8).reshape(-1, 136, 240, 3)
    keys = source[:, ::8, ::8, :].reshape(len(source), -1).astype(np.float32)
    for item in record['cases']:
        name = item['case']; row = {'case': name}
        for kind in ('rgb', 'pcm'):
            actual = decode(public/(name+'-actual.mkv'), kind)
            expected = decode(public/(name+'-expected.mkv'), kind)
            assert actual == expected, (name, kind)
            digest = 'sha256:'+hashlib.sha256(actual).hexdigest()
            assert digest == item[kind+'_sha256'], (name, kind)
            row[kind+'_sha256'] = digest
            if kind == 'rgb':
                row['frames'] = len(actual)//(240*136*3)
                if name in {'S01', 'S02'}:
                    first, last, source_first = (10, 50, 30) if name == 'S01' else (0, 60, 10)
                    query = np.frombuffer(actual, np.uint8).reshape(-1, 136, 240, 3)[first:last, ::8, ::8, :]
                    query = query.reshape(last-first, -1).astype(np.float32)
                    distances = np.mean((query[:, None, :]-keys[None, :, :])**2, axis=2)
                    found = distances.argmin(axis=1)
                    expected_ids = np.arange(source_first, source_first+last-first)
                    assert np.array_equal(found, expected_ids)
                    sorted_distance = np.sort(distances, axis=1)
                    identities.append({'case': name, 'frames': len(found), 'mismatches': 0,
                        'minimum_runner_up_mse_margin': float((sorted_distance[:, 1]-sorted_distance[:, 0]).min()),
                        'actual_source_frame_ids': found.tolist()})
            else:
                row['stereo_sample_frames'] = len(actual)//8
        assert row['frames'] == item['frames'] and row['stereo_sample_frames'] == item['stereo_sample_frames']
        cases.append(row)
    with Image.open(public/'comparison.gif') as gif:
        durations = []
        for index in range(gif.n_frames):
            gif.seek(index); durations.append(gif.info.get('duration', 0))
        gif_meta = {'width': gif.width, 'height': gif.height, 'encoded_frames': gif.n_frames,
                    'duration_ms': sum(durations)}
    assert gif_meta == {'width': 480, 'height': 272, 'encoded_frames': 20, 'duration_ms': 4000}
    result = {'status': 'passed', 'at_utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
        'source_frame_identities': identities, 'streams': streams,
        'video_streams': sum(s.get('codec_type') == 'video' for item in streams for s in item['streams']),
        'audio_streams': sum(s.get('codec_type') == 'audio' for item in streams for s in item['streams']),
        'gif': gif_meta, 'public_files': len([p for p in public.iterdir() if p.is_file()]),
        'public_bytes': sum(p.stat().st_size for p in public.iterdir() if p.is_file()),
        'public_sha256': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in public.iterdir() if p.is_file()},
        'generator_sha256': sha(Path(__file__)), 'source_unchanged': frozen() == record['source_after'],
        'continuous_playback_reviewed': False, 'listening_reviewed': False,
        'scope': 'Artifact hashes, actual/hand-authored fixed V39 RGB and PCM re-decode equality, two direct-source identity checks and local stream/GIF metadata. No independent original renderer or natural quality acceptance.'}
    assert result['source_unchanged']
    save(output, result)
    print(json.dumps({k: result[k] for k in ('status', 'public_files', 'public_bytes', 'video_streams', 'audio_streams')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.public.resolve(), args.output.resolve())
