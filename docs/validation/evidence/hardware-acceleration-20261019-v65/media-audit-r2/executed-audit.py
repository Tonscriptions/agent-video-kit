"""Independent decoded previews, historical provenance and retained native negatives."""
from __future__ import annotations
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/hardware-acceleration-20261019-v65'
ASSETS = ROOT/'docs/assets/hardware-acceleration-20261019-v65-r6'


def sha(path): return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--revision', choices=('r2', 'r3'), required=True)
    revision = parser.parse_args().revision
    output = BASE/('media-audit-'+revision); output.mkdir(exist_ok=False)
    preview = ASSETS/('preview-'+revision); preview.mkdir(exist_ok=False)
    shutil.copyfile(__file__, output/'executed-audit.py')
    calls = []; checks = []
    def run(values, label, expected=0):
        values = list(map(str, values)); p = subprocess.run(values, cwd=ROOT, capture_output=True, timeout=60)
        stdout, stderr = output/(label+'.stdout.log'), output/(label+'.stderr.log')
        stdout.write_bytes(p.stdout); stderr.write_bytes(p.stderr)
        calls.append({'id': label, 'command': values, 'exit_code': p.returncode, 'expected_exit': expected,
            'stdout': stdout.name, 'stderr': stderr.name, 'stdout_sha256': sha(stdout), 'stderr_sha256': sha(stderr)})
        save(output/'commands.json', calls)
        assert (p.returncode != 0 if expected == 'nonzero' else p.returncode == expected), label
        return p.stdout
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    for name, source in [('original', 'source-8bit.mkv'), ('edited', 'nvenc-cuda.mkv')]:
        path = preview/(name+'.mp4')
        run([ffmpeg, '-hide_banner', '-y', '-loglevel', 'error', '-i', ASSETS/source,
             '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', path], name+'-preview')
        probe = json.loads(run([ffprobe, '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', path], name+'-probe'))
        video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        assert video['nb_read_frames'] == '48' and video['r_frame_rate'] == '24/1'
        hashes = []
        for suffix, media in [('preview', path), ('original', ASSETS/source)]:
            raw = run([ffmpeg, '-v', 'error', '-i', media, '-map', '0:v:0', '-pix_fmt', 'yuv420p', '-f', 'framemd5', '-'], name+'-'+suffix+'-frames')
            hashes.append([line.split(',')[-2:] for line in raw.decode().splitlines() if line and not line.startswith('#')])
        assert hashes[0] == hashes[1]
        checks.append({'id': name+'-preview', 'frames': 48, 'fps': '24/1', 'decoded_video_unchanged': True,
            'audio': 'AAC transcoded for MP4 preview; not PCM equality evidence', 'probe': probe})
    # The initial lossless H.264 fixture is outside this GPU decoder's supported profile.
    # Retain an independent complete stderr after the old metadata rollback removed logs.
    lossless = ROOT/'docs/assets/hardware-acceleration-20261019-v65-r2/source-8bit.mkv'
    for backend in ('d3d11va', 'cuda'):
        values = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-hwaccel', backend,
            '-hwaccel_output_format', 'd3d11' if backend == 'd3d11va' else 'cuda', '-i', lossless,
            '-frames:v', '4', '-an', '-vf', 'hwdownload,format=nv12,format=yuv420p', '-f', 'framemd5', '-']
        run(values, 'lossless-h264-'+backend, expected='nonzero')
    historical = []
    for revision in range(2, 6):
        folder = ROOT/f'docs/assets/hardware-acceleration-20261019-v65-r{revision}'
        evidence = BASE/f'development-r{revision}'
        if not folder.is_dir(): continue
        inventory = {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in folder.iterdir() if p.is_file() and p.name != 'provenance.json'}
        generator = evidence/'executed-generator.py'
        save(folder/'provenance.json', {'license': 'CC0-1.0', 'author': 'Agent Video Kit contributors',
            'source': 'Original deterministic FFmpeg mathematical patterns/sine; see executed generator',
            'generator': str(generator.relative_to(ROOT)), 'generator_sha256': sha(generator), 'files': inventory,
            'scope': 'Historical development or failed fixture; not current acceptance, no listening/continuous review'})
        historical.append(str(folder.relative_to(ROOT)))
    durations = []
    with Image.open(ASSETS/'nvenc-cuda.gif') as im:
        for i in range(im.n_frames): im.seek(i); durations.append(im.info['duration'])
    assert len(durations) == 16 and sum(durations) == 2010
    files = {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in preview.iterdir()}
    save(preview/'provenance.json', {'license': 'CC0-1.0', 'generator_sha256': sha(output/'executed-audit.py'),
        'files': files, 'source_directory': str(ASSETS.relative_to(ROOT)), 'video_stream': 'copied',
        'audio_stream': 'AAC re-encoded; use primary MKV/PCM for equality checks', 'fps': '24/1', 'frames_each': 48})
    # This receipt records the actual contact-sheet inspection performed in the app.
    save(output/'static-review.json', {'reviewed_file': str((ASSETS/'contact-sheet.png').relative_to(ROOT)),
        'sha256': sha(ASSETS/'contact-sheet.png'), 'source_and_output_indices': [0, 24, 47],
        'reviewed_static_frames': 6, 'observation': 'Source counters 0/24/47 align; edited image shows the authored horizontal shift and brightness.',
        'continuous_playback': False, 'audio_listened': False, 'natural_quality_accepted': False})
    save(output/'verification.json', {'status': 'passed_scoped_media_audit', 'calls': calls, 'checks': checks,
        'historical_provenance': historical, 'gif_frames': 16, 'gif_durations_ms': durations, 'gif_duration_ms': 2010,
        'gif_audio': False, 'preview_frames_separate': 96, 'decoded_unchanged_preview_video': True,
        'lossless_h264_hardware_decode_negatives': 2, 'finished_at_utc': datetime.now(timezone.utc).isoformat()})
    print(json.dumps({'native_calls': len(calls), 'preview_frames_separate': 96, 'negative_cases': 2, 'gif_ms': sum(durations)}))


if __name__ == '__main__': main()
