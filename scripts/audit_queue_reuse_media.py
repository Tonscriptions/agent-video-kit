"""Bind actual V70 public media, release records and native FFprobe clocks."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/openfilm-batch-reuse-20261020-v70'
PREFIX = 'openfilm-batch-reuse-20261020-v70-'


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--prepare-release-records', action='store_true')
    args = p.parse_args()
    output = args.output.resolve()
    assert not output.exists()
    install = json.loads((BASE / 'installed-r1/verification.json').read_bytes())
    assert install['status'] == 'passed'
    public = ROOT / ('docs/assets/' + PREFIX + 'installed-r1')
    release = public / 'release'
    if args.prepare_release_records:
        release.mkdir(exist_ok=False)
        runtime = ROOT / 'product/.runtime/openfilm-batch-reuse-20261020-v70/installed-r1'
        shutil.copyfile(runtime / 'bundle/manifest.json', release / 'bundle-manifest.json')
        shutil.copyfile(runtime / 'installed/receipt.json', release / 'install-receipt.json')
        archive = runtime / 'bundle.zip'
        assert sha(archive) == install['bundle']['archive_sha256']
        (release / 'bundle-archive.json').write_text(json.dumps({
            'archive': 'bundle.zip', 'bytes': archive.stat().st_size,
            'sha256': sha(archive), 'manifest_sha256': install['bundle']['manifest_sha256'],
            'archive_location': 'local ignored runtime; not redistributed with the public demo',
            'python_ffmpeg_system_dlls_bundled': False,
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    assert sha(release / 'bundle-manifest.json') == install['bundle']['manifest_sha256']
    assert json.loads((release / 'install-receipt.json').read_bytes())['manifest_sha256'] == install['bundle']['manifest_sha256']
    files = []
    folders = sorted((ROOT / 'docs/assets').glob(PREFIX + '*'))
    for folder in folders:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                files.append({'path': path.relative_to(ROOT).as_posix(),
                              'bytes': path.stat().st_size, 'sha256': sha(path)})
    # Keep failed/old prototype bytes but only probe the final source and install runs.
    probes = []
    for suffix in ('native-r3', 'installed-r1'):
        folder = ROOT / ('docs/assets/' + PREFIX + suffix)
        for path in sorted(folder.iterdir()):
            if path.suffix not in ('.mkv', '.mp4', '.webm', '.gif'):
                continue
            command = ['ffprobe', '-v', 'error', '-count_frames', '-show_entries',
                       'stream=codec_type,codec_name,width,height,nb_read_frames,duration,sample_rate,channels:format=duration,size',
                       '-of', 'json', str(path)]
            run = subprocess.run(command, cwd=ROOT, capture_output=True, check=True, timeout=60)
            data = json.loads(run.stdout)
            video = next(s for s in data['streams'] if s['codec_type'] == 'video')
            assert int(video['nb_read_frames']) == (12 if path.suffix == '.gif' else 24)
            assert abs(float(data['format']['duration']) - 2) < 0.05
            if path.suffix == '.gif':
                assert (video['width'], video['height']) == (480, 270)
            probes.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path),
                           'command': command, 'probe': data})
    record = {'status': 'passed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'generator_sha256': sha(Path(__file__)), 'public_files': files,
              'final_media_probes': probes, 'static_review_record': 'static-review-r1.json',
              'continuous_playback_reviewed': False, 'audio_listening_reviewed': False,
              'natural_footage_quality_accepted': False, 'full_capcut_parity': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'status': record['status'], 'public_files': len(files),
                      'final_media_probes': len(probes), 'gif_frames': 12, 'gif_seconds': 2}))


if __name__ == '__main__':
    main()
