"""Supplement an existing release smoke: generated PS entry and local-path gates."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def run(work, evidence, public, contact_reviewed):
    record_path = evidence / 'verification.json'
    real = json.loads(record_path.read_bytes())
    assert real['status'] == 'passed' and real['process_calls'] == 29
    installed = work / 'independent-install'
    shell = shutil.which('pwsh') or shutil.which('powershell')
    assert shell
    env = os.environ.copy()
    temp = installed / 'runtime' / 'temp'
    temp.mkdir(parents=True, exist_ok=True)
    env.update(TEMP=str(temp), TMP=str(temp), PYTHONDONTWRITEBYTECODE='1', PIP_NO_INDEX='1')
    command = [shell, '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(installed / 'agent-video-kit.ps1'), 'version']
    result = subprocess.run(command, cwd=work, env=env, capture_output=True, encoding='utf-8', timeout=45)
    assert result.returncode == 0 and json.loads(result.stdout)['data']['schema_validation']['ok'], result.stderr
    write(evidence / 'powershell-launcher.json', {
        'command': command, 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr,
        'extra_native_process_calls': 1, 'main_smoke_process_calls': 29, 'main_guarded_cli_calls': 22,
        'bootstrap_sha256': {name: sha(installed / name) for name in ('run.py', 'agent-video-kit.ps1')},
        'generator_sha256': sha(Path(__file__)),
    })
    targets = [work / 'no-unc-install', work / 'no-uri-cancel-install']
    assert not any(path.exists() for path in targets)
    cases = [
        ('unc-bundle', ['--bundle', '//avk-invalid.local/share/bundle', '--target', str(targets[0])]),
        ('unc-target', ['--target', '//avk-invalid.local/share/install']),
        ('uri-cancel', ['--target', str(targets[1]), '--cancel-file', 'https://avk-invalid.local/cancel']),
    ]
    rows = []
    for name, arguments in cases:
        command = [sys.executable, '-I', '-B', '-X', 'utf8', str(work / 'bundle' / 'install.py'),
                   *arguments, '--manifest-sha256', real['bundle']['manifest_sha256']]
        result = subprocess.run(command, cwd=work, env=env, capture_output=True, encoding='utf-8', timeout=20)
        data = json.loads(result.stdout)
        assert result.returncode == 2 and data['code'] == 'NETWORK_PATH_FORBIDDEN', (name, data, result.stderr)
        rows.append({'name': name, 'command': command, 'exit_code': result.returncode, 'stdout': data, 'stderr': result.stderr})
    assert not any(path.exists() for path in targets)
    write(evidence / 'native-path-boundaries.json', {
        'status': 'passed', 'extra_native_process_calls': 3, 'cases': rows, 'no_install_targets_created': True,
        'mapped_drive_case': 'unit test injects native drive-type result; no network drive mounted',
        'generator_sha256': sha(Path(__file__)),
    })
    if contact_reviewed:
        contact = public / 'contact.png'
        assert sha(contact) == real['public_files']['contact.png']['sha256']
        real['static_review'] = {
            'reviewed': True, 'artifact': contact.relative_to(ROOT).as_posix(), 'sha256': sha(contact),
            'frame_indices': [0, 15, 29], 'observed_source_ids_before': [10, 25, 39],
            'observed_source_ids_after': [20, 35, 49],
            'scope': 'Manual inspection of three contact-sheet moments; no continuous playback or listening review',
        }
        record_path.write_text(json.dumps(real, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': 'passed', 'extra_native_process_calls': 4, 'contact_review_recorded': contact_reviewed}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--contact-reviewed', action='store_true', help='Only after separately viewing this exact contact sheet')
    args = parser.parse_args()
    run(args.work.resolve(), args.evidence.resolve(), args.public.resolve(), args.contact_reviewed)
