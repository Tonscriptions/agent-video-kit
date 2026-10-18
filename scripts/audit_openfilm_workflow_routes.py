"""Check fixed OpenFilm workflow sources and local CLI route declarations only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'product/src'))
from ai_ad_editor.cli import COMMANDS, build_parser

ROUTES = {
    'media ingest': ['--input', '--project'],
    'media understand': ['--beats', '--transcribe', '--adapter-id'],
    'media prepare': ['--thumbnail', '--waveform', '--at-seconds'],
    'media highlights': ['--top-k', '--min-duration', '--max-duration', '--apply'],
    'media track': ['--roi', '--adapter-id', '--object-id', '--clip-id'],
    'media track-bind': ['--target-clip-id', '--source-clip-id'],
    'subtitle transcribe': ['--adapter-id', '--apply'],
    'subtitle align': ['--granularity', '--apply'],
    'subtitle segment': ['--corrections', '--expected-input-sha256', '--apply'],
    'subtitle evaluate': ['--max-cer'],
    'tts synthesize': ['--adapter-id', '--voice-id', '--apply'],
    'motion list': ['--query'],
    'motion apply': ['--preset', '--start-tick', '--end-tick'],
    'motion html-source': ['--input'],
    'motion html-render': ['--source-asset-id', '--layout-check', '--apply'],
    'motion html-quality': ['--source-asset-id'],
    'timeline compose': ['--input', '--dry-run'],
    'timeline edit': ['--input', '--expected-project-sha256', '--dry-run'],
    'render': ['--project', '--output'],
    'quality check': ['--input', '--max-av-sync-ms'],
    'rights check': ['--target'],
    'policy audit': ['--project'],
}


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def run(output):
    if output.exists():
        raise ValueError('fresh research output required')
    before = frozen()
    archive = ROOT / 'sources/upstream/openfilm-refresh-20261019-r05/repo.zip'
    archive_sha = sha(archive.read_bytes())
    if archive_sha != 'sha256:6a5c784f96f037c232f728010818378d66164d3db6eebd3518a9831517192a66':
        raise ValueError('fixed R05 upstream archive required')
    sources = []
    with zipfile.ZipFile(archive) as package:
        prefix = 'openfilm-openfilm-7a64d1f/'
        for name in ('replicate', 'long-to-short', 'screen-demo'):
            path = 'packages/openfilm/skills/' + name + '/SKILL.md'
            raw = package.read(prefix + path)
            sources.append({'workflow': name, 'upstream_path': path, 'bytes': len(raw), 'sha256': sha(raw)})
        license_sha = sha(package.read(prefix + 'LICENSE'))
    parser = build_parser()
    checked = []
    for route, flags in ROUTES.items():
        words = route.split()
        current = parser
        for word in words:
            groups = [action for action in current._actions if isinstance(action, argparse._SubParsersAction)]
            if len(groups) != 1 or word not in groups[0].choices:
                raise ValueError('local parser route missing: ' + route)
            current = groups[0].choices[word]
        options = {flag for action in current._actions for flag in action.option_strings}
        if not set(flags).issubset(options):
            raise ValueError('local route flags missing: ' + route + ' ' + str(set(flags) - options))
        handler = COMMANDS.get((words[0], words[1] if len(words) > 1 else None))
        if not callable(handler):
            raise ValueError('local command handler missing: ' + route)
        checked.append({'route': route, 'required_declarations': flags, 'handler': handler.__name__})
    after = frozen()
    if before != after or len(before) != 188:
        raise ValueError('product inputs changed during research')
    result = {'status': 'passed_source_and_cli_declaration_mapping_only',
              'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'upstream_commit': '7a64d1feacdb59fb631694af7501a4ca570254ca',
              'upstream_archive_sha256': archive_sha, 'upstream_license_sha256': license_sha,
              'workflow_sources': sources, 'local_routes': checked, 'route_count': len(checked),
              'frozen_before': before, 'frozen_after': after, 'frozen_equal': True,
              'editing_commands_executed': 0, 'models_executed': 0, 'new_skills_installed': 0,
              'new_repaired_or_edited_outputs': 0, 'end_to_end_workflow_accepted': False,
              'browser_opened': False, 'network_used': False, 'virtualization_used': False,
              'generator_sha256': sha(Path(__file__).read_bytes())}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: result[key] for key in ('status', 'route_count', 'editing_commands_executed', 'new_skills_installed')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
