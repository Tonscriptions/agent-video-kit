"""Reject an actual local ffconcat file with a forged single-file probe label."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_frozen_regression import frozen


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'evidence', 'source'):
        p.add_argument('--'+name, type=Path, required=True)
    args = p.parse_args()
    work, evidence = args.work.resolve(), args.evidence.resolve()
    if work.exists() or evidence.exists():
        raise ValueError('Use new work and evidence directories')
    work.mkdir(parents=True)
    evidence.mkdir(parents=True)
    record = {'status': 'running', 'calls': [], 'frozen_before': frozen(), 'virtualization': False,
              'started_at_utc': datetime.now(timezone.utc).isoformat(), 'source': str(args.source.resolve())}
    def save():
        write(evidence/'verification.json', record)
    save()
    prefix = [sys.executable, '-E', '-B', '-X', 'utf8', '-c',
              'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;sys.exit(main())',
              str(ROOT/'product/src')]
    def run(label, command, expected=0):
        env = dict(os.environ)
        env.update(TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'),
                   TMPDIR=str(ROOT/'product/.runtime/temp'))
        result = subprocess.run([str(v) for v in command], cwd=ROOT, env=env, capture_output=True, timeout=120)
        (evidence/(label+'.stdout.log')).write_bytes(result.stdout)
        (evidence/(label+'.stderr.log')).write_bytes(result.stderr)
        record['calls'].append({'label': label, 'command': [str(v) for v in command], 'exit_code': result.returncode})
        save()
        assert result.returncode == expected, (label, result.returncode, result.stdout[-2000:], result.stderr[-1000:])
        return json.loads(result.stdout)
    try:
        project = work/'project'
        run('init', [*prefix, 'project', 'init', project])
        media = run('ingest', [*prefix, 'media', 'ingest', '--project', project, '--input', args.source.resolve(), '--asset-id', 'spoof'])
        value = json.loads((project/'project.json').read_bytes())
        asset = value['assets'][0]
        original = project/asset['uri']
        playlist = original.with_name('spoof.png')
        playlist.write_text("ffconcat version 1.0\nfile '"+original.name+"'\n", encoding='utf-8', newline='\n')
        actual = run('actual-probe', ['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
            '-show_format', '-show_streams', '-of', 'json', playlist])
        assert actual['format']['format_name'] == 'concat'
        asset['uri'] = playlist.relative_to(project).as_posix()
        asset['sha256'] = 'sha256:'+hashlib.sha256(playlist.read_bytes()).hexdigest()
        asset['probe']['format'] = 'png_pipe'
        write(project/'project.json', value)
        changes = work/'compose.json'
        write(changes, {'operations': [{'op': 'append_clip', 'track_id': 'track_video_1', 'asset_id': 'spoof',
             'source_in_tick': 0, 'source_out_tick': 90000}]})
        run('compose', [*prefix, 'timeline', 'compose', '--project', project, '--input', changes])
        jobs = work/'jobs.json'
        write(jobs, {'job_id': 'reject', 'output': 'renders/reject.mp4', 'profile': 'custom', 'width': 320, 'height': 180})
        run('enqueue', [*prefix, 'queue', 'enqueue', '--project', project, '--input', jobs])
        response = run('run', [*prefix, 'queue', 'run', '--project', project, '--reuse-identical', '--progress', 'jsonl'], 2)
        assert response['data']['jobs'][0]['error']['code'] == 'QUEUE_REUSE_UNSUPPORTED', response
        events = [json.loads(line) for line in (evidence/'run.stderr.log').read_text(encoding='utf-8').splitlines() if line.startswith('{')]
        assert not any(e.get('type') in {'render_started', 'reuse_started'} for e in events)
        assert not (project/'renders/reject.mp4').exists()
        assert not (project/'renders/reject.mp4.manifest.json').exists()
        record.update(status='passed_actual_concat_rejected_before_encode', declared_format='png_pipe',
                      actual_format='concat', response=response, events=events, cli_calls=5,
                      encoding_started_events=0, copied_outputs=0)
    except BaseException as exc:
        record.update(status='failed', error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        record.update(frozen_after=frozen(), finished_at_utc=datetime.now(timezone.utc).isoformat())
        record['frozen_equal'] = record['frozen_before'] == record['frozen_after']
        save()
    assert record['frozen_equal']
    print(json.dumps({'status': record['status'], 'frozen_equal': record['frozen_equal']}))


if __name__ == '__main__':
    main()
