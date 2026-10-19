"""Native CLI hardware deliveries, explicit failures, originals and reproducible media."""
from __future__ import annotations
import argparse
from array import array
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
TPS, FPS, W, H = 90000, 24, 320, 180


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8', newline='\n')


def main():
    parser = argparse.ArgumentParser()
    for flag in ('output', 'work', 'assets'):
        parser.add_argument('--'+flag, type=Path, required=True)
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    output, work, assets = [getattr(args, k).resolve() for k in ('output', 'work', 'assets')]
    for path in (output, work, assets): path.mkdir(parents=True, exist_ok=False)
    logs = output/'logs'; logs.mkdir()
    shutil.copyfile(__file__, output/'executed-generator.py')
    before = frozen(); calls = []; checks = []; artifacts = []
    env = dict(os.environ, TEMP=str(work), TMP=str(work), TMPDIR=str(work), PYTHONDONTWRITEBYTECODE='1')
    bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;sys.exit(main())'
    prefix = ([sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(args.installed.resolve()/'run.py')] if args.installed else
              [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap, str(ROOT/'product/src')])

    def command(values, label, expected=0, binary=False):
        values = list(map(str, values)); i = len(calls)+1
        result = subprocess.run(values, cwd=ROOT, env=env, capture_output=True, timeout=300)
        out = logs/f'{i:03d}-{label}.stdout.log'
        err = logs/f'{i:03d}-{label}.stderr.log'
        if binary:
            import gzip
            out = out.with_suffix('.raw.gz'); out.write_bytes(gzip.compress(result.stdout, mtime=0))
        else: out.write_bytes(result.stdout)
        err.write_bytes(result.stderr)
        calls.append({'id': label, 'command': values, 'exit_code': result.returncode, 'expected_exit': expected,
            'stdout': str(out.relative_to(output)), 'stderr': str(err.relative_to(output)),
            'stdout_sha256': sha(out), 'stderr_sha256': sha(err), 'raw_compressed': binary})
        save(output/'commands.json', calls)
        assert result.returncode == expected, label+' '+result.stdout.decode('utf8', 'replace')[-3000:]+' '+result.stderr.decode('utf8', 'replace')[-3000:]
        return result.stdout if binary else result.stdout.decode('utf-8-sig', 'replace')

    def cli(values, label, expected=0):
        return json.loads(command([*prefix, *values], label, expected))

    def check(name, condition, **details):
        checks.append({'id': name, 'passed': bool(condition), **details})
        assert condition, name

    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    command([ffmpeg, '-version'], 'ffmpeg-version')
    command(['nvidia-smi', '--query-gpu=name,memory.free,memory.total', '--format=csv,noheader'], 'gpu-readonly')
    for name, graph, codec, pix, extra in [
        ('source-8bit', f'testsrc2=size={W}x{H}:rate={FPS}', 'libx264', 'yuv420p', ['-crf', '12']),
        ('source-10bit', f"nullsrc=s={W}x{H}:r={FPS},format=yuv420p10le,geq=lum='64+mod(X*3+Y*5+N*7,876)':cb='512+32*sin(X/20)':cr='512+32*cos(Y/20)'",
         'libx265', 'yuv420p10le', ['-crf', '12', '-x265-params', 'log-level=error'])]:
        command([ffmpeg, '-hide_banner', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', graph,
            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '2', '-c:v', codec,
            '-preset', 'ultrafast', *extra, '-pix_fmt', pix, '-color_primaries', 'bt709', '-color_trc', 'bt709',
            '-colorspace', 'bt709', '-color_range', 'tv', '-c:a', 'pcm_s16le', assets/(name+'.mkv')], name)
    raw = command([ffmpeg, '-v', 'error', '-i', assets/'source-10bit.mkv', '-frames:v', '1', '-an',
                   '-pix_fmt', 'yuv420p10le', '-f', 'rawvideo', '-'], 'ten-bit-luma', binary=True)
    samples = array('H'); samples.frombytes(raw[:W*H*2])
    lowbits = sum(v % 4 != 0 for v in samples)
    check('source_has_native_low_two_bits', lowbits > W*H//2, nonzero_low_bits=lowbits, luma_samples=len(samples))

    projects = {}
    for depth in (8, 10):
        root = work/f'project-{depth}'; cli(['project', 'init', root], f'init-{depth}')
        source = assets/f'source-{depth}bit.mkv'
        cli(['media', 'ingest', '--project', root, '--input', source, '--asset-id', 'source'], f'ingest-{depth}')
        project_path = root/'project.json'; value = json.loads(project_path.read_bytes())
        value['settings']['canvas'].update(width=W, height=H)
        value['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
        value['settings']['output'] = {'container': 'mkv',
            'video': {'codec': 'libx264' if depth == 8 else 'libx265', 'preset': 'ultrafast', 'crf': 18,
                      'pixel_format': 'yuv420p' if depth == 8 else 'yuv420p10le', 'bitrate': '4M'},
            'audio': {'codec': 'pcm_s16le'}}
        save(project_path, value)
        changes = work/f'compose-{depth}.json'
        save(changes, {'operations': [
            {'op': 'add_sequence', 'id': 'child', 'duration_tick': 2*TPS},
            {'op': 'append_clip', 'sequence_id': 'child', 'track_id': 'child_video_1', 'id': 'leaf',
             'asset_id': 'source', 'source_in_tick': 0, 'source_out_tick': 2*TPS, 'timeline_start_tick': 0, 'duration_tick': 2*TPS,
             'effects': [{'type': 'brightness', 'parameters': {'brightness': .025}}],
             'keyframes': [{'property': 'transform.position.x', 'keyframes': [
                 {'at_tick': 0, 'value': .5, 'interpolation': 'linear'},
                 {'at_tick': 2*TPS, 'value': .55, 'interpolation': 'linear'}]}]},
            {'op': 'append_sequence_clip', 'sequence_id': 'seq_main', 'track_id': 'track_video_1', 'id': 'group',
             'nested_sequence_id': 'child', 'source_in_tick': 0, 'source_out_tick': 2*TPS, 'timeline_start_tick': 0, 'duration_tick': 2*TPS}]})
        cli(['timeline', 'compose', '--project', root, '--input', changes], f'compose-{depth}')
        projects[depth] = root

    def render(name, depth=8, extra=(), expected=0, output_name=None):
        root = projects[depth]; target = root/'renders'/((output_name or name)+'.mkv')
        value = cli(['render', '--project', root, '--output', target, *extra], name, expected)
        if expected:
            return value
        manifest = json.loads(target.with_suffix('.mkv.manifest.json').read_bytes())
        acceleration = manifest['acceleration']
        check(name+'-verified', acceleration['status'] in ('planned', 'verified'))
        probe = json.loads(command([ffprobe, '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', target], name+'-probe'))
        video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        check(name+'-clock', int(video['nb_read_frames']) == 48 and video['r_frame_rate'] == '24/1')
        pcm = command([ffmpeg, '-v', 'error', '-i', target, '-map', '0:a:0', '-c:a', 'pcm_s16le', '-f', 's16le', '-'], name+'-audio', binary=True)
        audio = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
        check(name+'-samples', len(pcm)//(2*audio['channels']) == 96000)
        destination = assets/(name+'.mkv'); shutil.copyfile(target, destination)
        shutil.copyfile(target.with_suffix('.mkv.manifest.json'), output/(name+'.manifest.json'))
        report = Path(acceleration['report']) if acceleration['report'] else None
        if report:
            shutil.copytree(report.parent, output/(name+'-acceleration'))
        artifacts.append({'id': name, 'path': str(destination.relative_to(ROOT)), 'sha256': sha(destination),
            'frames': 48, 'fps': '24/1', 'authored_seconds': 2, 'audio_sample_frames': 96000,
            'actual_encoder': acceleration.get('selected_encoder') or manifest['settings']['output']['video']['codec'],
            'decoders': acceleration.get('selected_decoders', {}), 'probe': probe})
        return manifest

    hw = ['--hardware-encode', 'require', '--hardware-encoder', 'nvenc', '--hardware-decode', 'require']
    for name, depth, decoder in [('nvenc-d3d11', 8, 'd3d11va'), ('nvenc-cuda', 8, 'cuda'), ('hevc10-cuda', 10, 'cuda')]:
        manifest = render(name, depth, [*hw, '--hardware-decoder', decoder])
        acceleration = manifest['acceleration']
        check(name+'-backend', acceleration['selected_encoder'] == ('h264_nvenc' if depth == 8 else 'hevc_nvenc'))
        check(name+'-forced-decode', bool(acceleration['selected_decoders']) and
              all(v['backend'] == decoder for v in acceleration['selected_decoders'].values()))

    render('cpu-control')
    fallback = render('amf-prefer', extra=['--hardware-encode', 'prefer', '--hardware-encoder', 'amf'])
    check('amf-physical-failure-fallback', fallback['acceleration']['selected_encoder'] is None and bool(fallback['acceleration']['decisions']))
    root = projects[8]; old = root/'renders/protected.mkv'; old.write_bytes(b'prior-output')
    failed = render('amf-require', extra=['--hardware-encode', 'require', '--hardware-encoder', 'amf'], expected=6, output_name='protected')
    check('required-physical-failure-keeps-output', old.read_bytes() == b'prior-output' and failed['errors'][0]['code'] == 'HARDWARE_REQUIRED_UNAVAILABLE')
    failed_operation = json.loads((root/'operations'/f'{failed["operation_id"]}.json').read_bytes())
    failed_report = Path(failed_operation['plan']['acceleration']['report'])
    check('failed-probe-logs-survive-cli-rollback', failed_report.is_file() and
        bool(list(failed_report.parent.glob('encoder-*.stderr.log'))))
    for mode in ('prefer', 'require'):
        value = render('budget-'+mode, extra=['--hardware-encode', mode, '--hardware-probe-mib', '1'], expected=6 if mode == 'require' else 0)
        if mode == 'prefer': check('budget-falls-back', value['acceleration']['selected_encoder'] is None)
    # Cancellation before hardware preflight; resume must make fresh real probes.
    marker = work/'cancel'; marker.write_text('cancel', encoding='utf8')
    cancelled = render('cancel-before-probe', extra=[*hw, '--hardware-decoder', 'cuda', '--cancel-file', str(marker)], expected=8)
    operation_id = cancelled['operation_id']; marker.unlink()
    resumed = cli(['render', '--project', root, '--resume', operation_id], 'resume-fresh-hardware')
    check('resume-succeeded', resumed['ok'])
    resume_op = json.loads((root/'operations'/f'{operation_id}.json').read_bytes())
    cancel_report = resume_op['plan']['acceleration']
    check('cancel-had-no-probes', cancel_report['status'] == 'cancelled' and cancel_report['probes'] == [])
    dry = cli(['render', '--project', root, '--dry-run', *hw], 'dry-run')
    check('dry-run-no-hardware', dry['ok'] and not (root/'renders/diagnostics'/('acceleration_'+dry['data']['plan']['operation_id'])).exists())
    jobs = work/'queue.json'; save(jobs, {'job_id': 'gpu', 'output': 'renders/queue.mp4', 'video_bitrate': '4M',
        'hardware_encode': 'require', 'hardware_encoder': 'nvenc', 'hardware_decode': 'require', 'hardware_decoder': 'cuda'})
    cli(['queue', 'enqueue', '--project', root, '--input', jobs], 'queue-enqueue')
    queued = cli(['queue', 'run', '--project', root], 'queue-run')
    check('queue-succeeded', queued['ok'])
    queued_manifest = json.loads((root/'renders/queue.mp4.manifest.json').read_bytes())
    check('queue-policy-used', queued_manifest['acceleration']['selected_encoder'] == 'h264_nvenc' and
          queued_manifest['settings']['acceleration']['decode'] == 'require')
    # Fair same-filter comparison; fidelity metrics are observations, not parity acceptance.
    psnr = command([ffmpeg, '-hide_banner', '-i', assets/'nvenc-cuda.mkv', '-i', assets/'cpu-control.mkv',
        '-lavfi', '[0:v][1:v]psnr', '-an', '-f', 'null', '-'], 'same-graph-psnr')
    command([ffmpeg, '-hide_banner', '-y', '-loglevel', 'error', '-i', assets/'nvenc-cuda.mkv',
        '-vf', 'fps=8,scale=320:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',
        '-loop', '0', assets/'nvenc-cuda.gif'], 'gif')
    # Archive every failure/cancel operation and its report, including failed probes.
    for depth, root in projects.items():
        shutil.copytree(root/'operations', output/f'operations-{depth}')
        if (root/'renders/diagnostics').is_dir(): shutil.copytree(root/'renders/diagnostics', output/f'diagnostics-{depth}')
    after = frozen()
    record = {'status': 'completed', 'started_scope': 'native-installed' if args.installed else 'native-development',
        'finished_at_utc': datetime.now(timezone.utc).isoformat(), 'calls': calls, 'checks': checks, 'artifacts': artifacts,
        'frozen_before': before, 'frozen_after': after, 'frozen_equal': before == after,
        'rights': 'All inputs are original deterministic FFmpeg mathematical patterns and sine tones, CC0-1.0.',
        'scope': ['four-frame hardware decode equality, full output structural decode and clocks',
                  '10-bit source low bits and output format; internal compositor precision is not accepted as 10-bit',
                  'no natural-media visual or listening or CapCut equivalence acceptance', 'no speed claim'],
        'browser_started': False, 'virtualization': False}
    save(output/'verification.json', record)
    assert before == after
    print(json.dumps({'calls': len(calls), 'checks': len(checks), 'artifacts': len(artifacts), 'frozen_equal': before == after}))


if __name__ == '__main__':
    try: main()
    except Exception:
        import traceback
        if '--output' in sys.argv:
            path = Path(sys.argv[sys.argv.index('--output')+1])
            if path.is_dir():
                save(path/'failure.json', {'status': 'failed', 'traceback': traceback.format_exc(),
                    'script_sha256': sha(Path(__file__)), 'time_utc': datetime.now(timezone.utc).isoformat()})
        raise
