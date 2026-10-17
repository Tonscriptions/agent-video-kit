"""Validate registered local video Skills and resolve their local references."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.parse


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def run(output):
    assert not output.exists(), output
    validator = Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
    results = []
    for folder in sorted((ROOT/'skills').iterdir()):
        if not folder.is_dir():
            continue
        source = folder/'SKILL.md'
        assert folder.name.startswith('video-cut-') and source.is_file(), folder
        process = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(validator), str(folder)],
                                 capture_output=True, timeout=30)
        assert process.returncode == 0, (folder, process.stdout, process.stderr)
        links = 0
        for path in folder.rglob('*.md'):
            for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',
                                  path.read_text(encoding='utf-8-sig')):
                target = raw.strip('<>').split('#', 1)[0]
                if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                    continue
                assert (path.parent/urllib.parse.unquote(target)).resolve().exists(), (path, target)
                links += 1
        installed = Path('C:/Users/carzy/.codex/skills')/folder.name
        assert installed.resolve() == folder.resolve(), installed
        results.append({'skill': folder.name, 'validator_exit_code': process.returncode,
                        'validator_stdout': process.stdout.decode('utf-8').strip(),
                        'validator_stderr': process.stderr.decode('utf-8').strip(),
                        'sha256': sha(source), 'local_links_checked': links,
                        'installed_directory_resolves_to_repo': True})
    assert len(results) == 14
    record = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'validator': str(validator),
              'validator_sha256': sha(validator), 'skill_count': len(results),
              'local_links_checked': sum(item['local_links_checked'] for item in results),
              'generator_sha256': sha(Path(__file__)), 'results': results}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: record[key] for key in ('skill_count', 'local_links_checked')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve())
