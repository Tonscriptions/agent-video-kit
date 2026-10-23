"""Validate registered Skills and exercise their actual installed CLI launcher."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


def validate_registered_skills(manifest):
    discovery = Path(manifest['codex_skills_directory'])
    validator_path = discovery / '.system/skill-creator/scripts/quick_validate.py'
    spec = importlib.util.spec_from_file_location('local_skill_validator', validator_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for entry in manifest['skills']:
        canonical = ROOT / 'skills' / entry['name']
        registered = discovery / entry['name']
        assert registered.is_junction() and registered.resolve() == canonical.resolve(), entry['name']
        valid, message = module.validate_skill(registered)
        assert valid, (entry['name'], message)
        text = (registered / 'SKILL.md').read_text('utf8')
        assert sha(registered / 'SKILL.md') == entry['skill_md_sha256'], entry['name']
        front = yaml.safe_load(text.split('---', 2)[1])
        ui = yaml.safe_load((registered / 'agents/openai.yaml').read_text('utf8'))['interface']
        assert front['name'] == entry['name'] and '$' + entry['name'] in ui['default_prompt']
        assert 25 <= len(ui['short_description']) <= 64, entry['name']
        links = []
        for label, target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text):
            resolved = (registered / target).resolve()
            assert resolved.is_file(), (entry['name'], target)
            links.append({'target': target, 'resolved': str(resolved)})
        legacy = ROOT / 'skills' / entry['legacy_name'] / 'SKILL.md'
        assert sha(legacy) == entry['legacy_skill_sha256'], entry['legacy_name']
        rows.append({'name': entry['name'], 'format_valid': valid, 'registration_junction': str(registered),
                     'target': str(registered.resolve()), 'skill_sha256': sha(registered / 'SKILL.md'),
                     'links': links, 'legacy_unchanged': True})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', type=Path, required=True, help='new evidence directory')
    ap.add_argument('--cases', type=Path, required=True, help='existing successful installed case run')
    args = ap.parse_args()
    if args.evidence.exists():
        raise SystemExit('Existing verification evidence is preserved')
    args.evidence.mkdir(parents=True)
    manifest = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    rows = validate_registered_skills(manifest)
    discovery = Path(manifest['codex_skills_directory'])
    save(args.evidence / 'skills.json', rows)
    launcher = discovery / 'agent-ffmpeg-local-editor/scripts/run.ps1'
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(launcher)]
    project = args.cases / 'project'
    output = project / 'renders/skill verified 成片.mp4'
    commands = [
        ('version', ['version'], 0),
        ('doctor', ['doctor'], 0),
        ('capabilities', ['capabilities'], 0),
        ('validate', ['validate', '--project', str(project)], 0),
        ('preview', ['preview', 'frame', '--project', str(project), '--frame', '60'], 0),
        ('render', ['render', '--project', str(project), '--output', str(output),
                    '--width', '360', '--height', '640', '--publish'], 0),
        ('quality', ['quality', 'check', '--project', str(project), '--input', str(output),
                     '--width', '360', '--height', '640', '--require-audio'], 0),
        ('remote-refused', ['media', 'ingest', '--project', str(project),
                            '--input', str(ROOT / 'docs/assets/local-install-20261024-r1/input/card-1.png'),
                            '--source-url', 'https://example.invalid/asset.png'], 2),
    ]
    runtime = json.loads((ROOT / manifest['runtime_config']).read_bytes())
    installed = Path(runtime['installed_directory'])
    results = []
    for label, arguments, expected in commands:
        started = time.monotonic()
        proc = subprocess.run(prefix + arguments, cwd=ROOT, capture_output=True, timeout=300,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (args.evidence / (label + '.stdout.json')).write_bytes(proc.stdout)
        (args.evidence / (label + '.stderr.txt')).write_bytes(proc.stderr)
        response = json.loads(proc.stdout)
        result = {'label': label, 'argv': prefix + arguments, 'exit_code': proc.returncode,
                  'expected_exit_code': expected, 'seconds': round(time.monotonic() - started, 3),
                  'ok': response['ok'], 'status': response['status'],
                  'stdout_sha256': sha(args.evidence / (label + '.stdout.json'))}
        results.append(result)
        save(args.evidence / 'commands.json', results)
        assert proc.returncode == expected and response['ok'] == (expected == 0), result
        if label == 'version':
            schema = Path(response['data']['schema_validation']['path'])
            assert schema.is_relative_to(installed / 'site/ai_ad_editor'), schema
        elif label == 'doctor':
            save(args.evidence / 'doctor-data.json', response['data'])
    source = project / 'renders/field.mp4'
    report = {'status': 'passed', 'date_utc': datetime.now(timezone.utc).isoformat(),
              'release': runtime['release'], 'registered_skills': len(rows),
              'skill_launcher_commands': len(results),
              'successes': sum(r['exit_code'] == 0 for r in results),
              'expected_refusals': sum(r['exit_code'] == 2 for r in results),
              'launcher_from_codex_discovery': str(launcher), 'installed_directory': str(installed),
              'installed_schema_provenance_checked': True,
              'spaces_and_chinese_path_forwarded': str(output),
              'output_bytes': output.stat().st_size, 'output_sha256': sha(output),
              'same_media_as_direct_installed_case': sha(output) == sha(source),
              'native_windows': True, 'virtual_environments_created': 0,
              'new_model_inferences': 0, 'continuous_playback_review': False, 'human_listening': False,
              'resolved_during_smoke': 'Explicit stdout/stderr inheritance fixed Windows hidden-child JSON forwarding; all eight final calls return structured JSON.'}
    save(args.evidence / 'verification.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
