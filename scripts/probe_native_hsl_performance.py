"""Compare native and expression HSL costs without changing color semantics."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'product/src'))
from ai_ad_editor.selective_hsl import compile_filter
from ai_ad_editor.hsl_native import compile_native


def sha(path): return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); output = args.output.resolve()
    assert output.is_relative_to(ROOT/'docs') and not output.exists()
    output.parent.mkdir(parents=True, exist_ok=True)
    binary = Path(shutil.which('ffmpeg')).resolve(strict=True)
    before = frozen()
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'generator_sha256': sha(__file__), 'binary': str(binary), 'binary_sha256': sha(binary),
              'native_windows': sys.platform == 'win32', 'network': False, 'virtualization': False,
              'frozen_before': before, 'width': 1920, 'height': 1080, 'fps': 30,
              'frames_per_case': 3, 'filter_threads': 1, 'repetitions': 1, 'calls': [], 'cases': [],'native_filter_frames':60,
              'benchmark_scope': 'native FFmpeg filter-to-null, including process startup; simultaneous regression load; no encoding, audio, CLI project or natural-footage acceptance',
              'real_time_accepted': False, 'full_capcut_parity': False}

    def save(): output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    def run(label, arguments):
        command = [str(binary), *map(str, arguments)]
        started = time.perf_counter()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=600,
                                env={**os.environ, 'TEMP': str(ROOT/'product/.runtime/temp'), 'TMP': str(ROOT/'product/.runtime/temp')})
        elapsed = time.perf_counter()-started
        logs = {}
        for stream in ('stdout', 'stderr'):
            path = output.with_name(output.stem+'-'+label+'.'+stream+'.log')
            assert not path.exists(); path.write_bytes(getattr(result, stream))
            logs[stream] = {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}
        record['calls'].append({'label': label, 'command': command, 'exit_code': result.returncode, 'wall_seconds': elapsed, 'logs': logs})
        save(); assert result.returncode == 0, label
        return elapsed, result
    save()
    try:
        run('version', ['-version']); run('geq-help', ['-hide_banner', '-h', 'filter=geq'])
        settings = [('control', None), ('red-hue', {'red_hue': 45}),
                    ('eight-band', {'red_hue': 35, 'orange_saturation': .3, 'yellow_lightness': -.2,
                                    'green_hue': 30, 'cyan_saturation': -.4, 'blue_hue': -25,
                                    'purple_lightness': .2, 'magenta_saturation': .2, 'intensity': .7})]
        settings.extend([('native-red-hue',settings[1][1]),('native-eight-band',settings[2][1])])
        for label, parameters in settings:
            kernel, metadata = ('format=gbrap', None) if parameters is None else compile_filter(
                {'type': 'selective_hsl', 'parameters': parameters}, lambda names, default: str(default))
            frames=3
            if label.startswith('native-'):
                kernel, metadata=compile_native({'type':'selective_hsl','parameters':parameters},lambda names,default:str(default),kernel,metadata)
                assert metadata['backend']=='ffmpeg:frei0r'
                frames=60
            seconds, result = run(label, ['-hide_banner', '-nostdin', '-v', 'error', '-filter_threads', '1',
                '-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=30', '-vf', kernel,
                '-frames:v', str(frames), '-an', '-f', 'null', '-', '-progress', 'pipe:1', '-nostats'])
            progress = result.stdout.decode('utf8', 'replace')
            actual_frames = int([line.split('=', 1)[1] for line in progress.splitlines() if line.startswith('frame=')][-1])
            assert actual_frames == frames and 'progress=end' in progress
            record['cases'].append({'name': label, 'kernel': metadata, 'actual_frames': actual_frames,
                'wall_seconds': seconds, 'seconds_per_frame': seconds/actual_frames,
                'observed_frames_per_wall_second': actual_frames/seconds,
                '30fps_wall_target_met_in_this_probe': actual_frames/seconds >= 30})
            save()
        record['status'] = 'passed-execution-probe'
    except BaseException as exc:
        record.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)}); raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), frozen_after=frozen())
        record['frozen_equal'] = record['frozen_after'] == before; save()
    assert record['frozen_equal']
    print(json.dumps({'status': record['status'], 'cases': [{k:v for k,v in c.items() if k!='kernel'} for c in record['cases']]}))


if __name__ == '__main__': main()
