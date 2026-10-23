"""Install the pinned public alpha locally on E:, without downloads or a venv."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v0.1.0-alpha.1'
ZIP_SHA = 'd306218ec889fd1cd591cd2536f651d58b13c23c2a7225b5b7fbadc4cfa6603a'
MANIFEST_SHA = 'sha256:ec7cb9216402c02726c8f53d1b305bb8e567b4b3d715a5793dc8000957420596'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


def plain_local(path):
    path = Path(path).absolute()
    if path.drive.casefold() != ROOT.drive.casefold() or path.anchor.startswith('\\\\'):
        raise ValueError('Installation and evidence must stay on the project drive')
    for part in reversed((path, *path.parents)):
        try:
            info = part.stat(follow_symlinks=False)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('Reparse path is not an installation destination: ' + str(part))
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--target', type=Path, default=ROOT / 'local/agent-ffmpeg' / TAG)
    ap.add_argument('--evidence', type=Path, required=True, help='new evidence directory, under docs/')
    args = ap.parse_args()
    target, evidence = plain_local(args.target), plain_local(args.evidence)
    if not target.is_relative_to(ROOT / 'local/agent-ffmpeg') or not evidence.is_relative_to(ROOT / 'docs'):
        raise ValueError('Use owned local/agent-ffmpeg and docs evidence directories')
    config = ROOT / 'local/agent-ffmpeg/runtime.json'
    if target.exists() or evidence.exists() or config.exists():
        raise ValueError('Existing installation/configuration/evidence is preserved')
    archive = ROOT / 'docs/releases' / TAG / 'artifacts' / ('agent-video-kit-' + TAG + '-cp313-win_amd64.zip')
    if sha(archive) != ZIP_SHA:
        raise ValueError('Public release ZIP SHA-256 mismatch')
    # Review all member names before extracting into a new, non-reparse directory.
    with zipfile.ZipFile(archive) as zipped:
        seen = set()
        total = 0
        for member in zipped.infolist():
            name = member.filename.rstrip('/')
            path = PurePosixPath(name)
            if (not name or path.is_absolute() or path.as_posix() != name
                    or any(part in {'.', '..'} for part in path.parts)
                    or '\\' in name or ':' in name or name.casefold() in seen
                    or stat.S_ISLNK(member.external_attr >> 16)):
                raise ValueError('Invalid release ZIP member: ' + name)
            seen.add(name.casefold())
            total += member.file_size
        if total > 128 * 1024**2:
            raise ValueError('Release extraction exceeds budget')
        version = json.loads(zipped.read('version.json'))
        if version['release'] != TAG or version['manifest_sha256'] != MANIFEST_SHA:
            raise ValueError('Release metadata does not match the pinned manifest')
        target.mkdir(parents=True)
        extracted = target / 'release'
        zipped.extractall(extracted)
    evidence.mkdir(parents=True)
    installed = target / 'installed'
    command = [sys.executable, '-I', '-B', '-X', 'utf8', str(extracted / 'bundle/install.py'),
               '--target', str(installed), '--manifest-sha256', MANIFEST_SHA]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=240,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (evidence / 'install.stdout.json').write_bytes(result.stdout)
    (evidence / 'install.stderr.txt').write_bytes(result.stderr)
    if result.returncode or not json.loads(result.stdout).get('ok'):
        raise RuntimeError('Offline installation failed; evidence preserved at ' + str(evidence))
    runtime = {'release': TAG, 'python': sys.executable,
               'installed_directory': str(installed), 'manifest_sha256': MANIFEST_SHA,
               'launcher_sha256': sha(installed / 'run.py'), 'zip_sha256': ZIP_SHA,
               'native_only': True}
    save(config, runtime)
    receipt = {'status': 'installed', 'installed_at_utc': datetime.now(timezone.utc).isoformat(),
               'release_archive': str(archive), 'archive_bytes': archive.stat().st_size,
               'archive_sha256': sha(archive), 'extracted_directory': str(extracted),
               'runtime_config': str(config), 'command': command, 'runtime': runtime,
               'network_downloads': 0, 'virtual_environment_created': False,
               'runtime_files': sum(p.is_file() for p in installed.rglob('*')),
               'runtime_bytes': sum(p.stat().st_size for p in installed.rglob('*') if p.is_file())}
    save(target / 'installation.json', receipt)
    save(evidence / 'installation.json', receipt)
    for name in ('receipt.json', 'dependency-audit.json', 'install.log'):
        (evidence / name).write_bytes((installed / name).read_bytes())
    print(json.dumps({'ok': True, 'release': TAG, 'installed': str(installed),
                      'runtime_config': str(config), 'evidence': str(evidence)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
