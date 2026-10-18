"""Archive the first failed VACE project's input-only publication state."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def run(output):
    archived = output.with_suffix('.project.json')
    if output.exists() or archived.exists():
        raise ValueError('fresh state observation and archive required')
    project = ROOT / 'product/.runtime/cuda-admission-vace-real-20261019-v60/actual/project'
    failure = ROOT / 'docs/validation/evidence/cuda-admission-vace-20261019-v60/r1-worker-response.json'
    response = json.loads(failure.read_bytes())
    raw = (project / 'project.json').read_bytes()
    value = json.loads(raw)
    assets = value['assets']
    expected = {response['source_sha256'], response['mask_sha256']}
    if len(assets) != 2 or {asset['sha256'] for asset in assets} != expected:
        raise ValueError('failed project must contain the two original inputs only')
    records = []
    for asset in assets:
        path = (project / asset['uri']).resolve()
        if not path.is_relative_to((project / 'assets').resolve()):
            raise ValueError('input asset escaped managed assets')
        data = path.read_bytes()
        if sha(data) != asset['sha256']:
            raise ValueError('failed project input bytes changed')
        records.append({'asset_id': asset['id'], 'uri': asset['uri'],
                        'sha256': sha(data), 'bytes': len(data)})
    managed = {path.resolve() for path in (project / 'assets').rglob('*') if path.is_file()}
    if managed != {(project / asset['uri']).resolve() for asset in assets}:
        raise ValueError('unexpected unpublished payload in managed assets')
    clips = [clip for sequence in value['sequences'] for track in sequence['tracks'] for clip in track['clips']]
    commands = [item['command'] for item in value['provenance']['change_log']]
    if clips or value['outputs'] or commands != ['media.ingest', 'media.ingest', 'media.adapter.register']:
        raise ValueError('unexpected output, timeline clip or completed inpainting operation')
    if (project / 'project.json').read_bytes() != raw:
        raise ValueError('project changed during read-only observation')
    output.parent.mkdir(parents=True, exist_ok=True)
    archived.write_bytes(raw)
    result = {'status': 'observed_failed_project_inputs_only_no_repaired_publication',
              'observed_at_utc': datetime.now(timezone.utc).isoformat(),
              'source_project': (project / 'project.json').relative_to(ROOT).as_posix(),
              'archived_project': archived.relative_to(ROOT).as_posix(),
              'project_sha256': sha(raw), 'worker_response_sha256': sha(failure.read_bytes()),
              'managed_assets': records, 'managed_asset_files': len(managed),
              'timeline_clips': len(clips), 'project_outputs': len(value['outputs']),
              'completed_commands': commands, 'repaired_output_registered': False,
              'project_modified': False, 'model_executed': False,
              'generator_sha256': sha(Path(__file__).read_bytes())}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: result[key] for key in ('status', 'managed_asset_files', 'timeline_clips', 'project_outputs')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
